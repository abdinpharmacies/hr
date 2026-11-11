"""Best-effort asynchronous observability; never owns a migration transaction."""
import contextlib
from pathlib import Path
import sys
import time
import uuid
from progress import Reporter, monitor_factory, format_event

_active=None


def format_status(event):
    text=format_event(event)
    total=event.get('total')
    processed=event.get('processed')
    if total and processed is not None and event.get('operation')=='COPY FROM':
        text+=f' progress={min(100,100*processed/total):.1f}%'
    if event.get('bytes_total'):
        text+=f' bytes_total={event["bytes_total"]:,}'
    if event.get('bytes_read') is not None:
        text+=f' file_bytes_read={event["bytes_read"]:,}'
    if event.get('table_index'):
        text+=f' table={event["table_index"]}/{event["table_count"]}'
    database=event.get('database',{})
    if database.get('index_phase'):
        text+=' index_phase='+database['index_phase']
        for field in ('blocks_done','blocks_total','tuples_done','tuples_total'):
            if database.get(field) is not None:
                text+=f' {field}={database[field]:,}'
    return text


def sample(connection, oid, pid, started):
    """Never read query text/values, and reject reused PID/database identities."""
    with connection.cursor() as cr:
        cr.execute('SELECT state,wait_event_type,wait_event,extract(epoch FROM clock_timestamp()-query_start),'
                   'pg_blocking_pids(pid) FROM pg_stat_activity WHERE datid=%s AND pid=%s AND backend_start=%s::timestamptz',
                   [oid,pid,started])
        row=cr.fetchone()
        if not row:
            return dict(state='registered backend unavailable')
        state,wait_type,wait,seconds,blockers=row
        result=dict(state=state,wait_type=wait_type,wait_event=wait,query_seconds=float(seconds or 0),blockers=blockers)
        cr.execute("SELECT to_regclass('pg_catalog.pg_stat_progress_copy') IS NOT NULL")
        if cr.fetchone()[0]:
            cr.execute('SELECT tuples_processed,bytes_processed FROM pg_stat_progress_copy WHERE pid=%s AND datid=%s',[pid,oid])
            copy=cr.fetchone()
            if copy:
                result.update(copy_rows=copy[0],copy_bytes=copy[1])
        # Index progress is optional and version-dependent. Keep COPY samples if unavailable.
        try:
            cr.execute("SELECT to_regclass('pg_catalog.pg_stat_progress_create_index') IS NOT NULL")
            if cr.fetchone()[0]:
                cr.execute('SELECT phase,blocks_done,blocks_total,tuples_done,tuples_total '
                           'FROM pg_stat_progress_create_index WHERE pid=%s AND datid=%s',[pid,oid])
                index=cr.fetchone()
                if index:
                    result.update(zip(('index_phase','blocks_done','blocks_total','tuples_done','tuples_total'),index))
        except Exception:
            result['index_phase']='index statistics unavailable'
        return result


class PreparedReporter(Reporter):
    def __init__(self,stage,config,interval=5,stream=None):
        self.paused=True
        self.factory=monitor_factory(config,'postgres')
        super().__init__(stage,stream=stream,interval=interval)

    def _console(self,event):
        if not self.paused:
            self.stream.write((event.get('text','') if event['kind']=='log' else format_status(event))+'\n')
            self.stream.flush()

    def begin(self,*args,**kwargs):
        self.paused=False
        return super().begin(*args,**kwargs)

    def emit(self,important=False):
        if not self.paused or important:
            super().emit(important)

    def pause(self):
        self.paused=True
        self.update(status='waiting for approval')
        self.emit(True)

    def finish(self,status='complete; pending commit'):
        with self.lock:
            self.state.update(status=status,monitor=False,operation_id=uuid.uuid4().hex)
        self.emit(True)

    def bind_target(self,connection,gate):
        pid=connection.get_backend_pid()
        # Called on the controller thread. Monitor thread owns a different connection.
        with gate.control.cursor() as cr:
            cr.execute('SELECT backend_start::text FROM pg_stat_activity WHERE datid=%s AND pid=%s',[gate.oid,pid])
            row=cr.fetchone()
        if row:
            with self.lock:
                self.backend=(gate.oid,pid,row[0])

    def _monitor(self):
        connection=None
        while not self.stop.wait(self.interval):
            with self.lock:
                state=dict(self.state)
                backend=self.backend
            if self.paused:
                continue
            token=state.get('operation_id')
            try:
                if state.get('file_path'):
                    path=Path(state['file_path'])
                    self.update(token=token,bytes=path.stat().st_size if path.exists() else 0)
                if not state.get('monitor') or backend is None:
                    continue
                if connection is None:
                    connection=self.factory()
                observation=sample(connection,*backend)
                values=dict(database=observation)
                if state.get('operation')=='COPY FROM' and 'copy_rows' in observation:
                    values.update(processed=observation['copy_rows'],bytes=observation['copy_bytes'])
                self.update(token=token,**values)
            except Exception as exc:
                self.update(token=token,database=dict(state='monitor unavailable',error_type=type(exc).__name__))
                if connection:
                    with contextlib.suppress(Exception):
                        connection.close()
                connection=None
        if connection:
            with contextlib.suppress(Exception):
                connection.close()


def start(stage,config):
    global _active
    try:
        _active=PreparedReporter(stage,config)
    except Exception:
        _active=None


def _call(method,*args,**kwargs):
    if _active is not None:
        try:
            return getattr(_active,method)(*args,**kwargs)
        except Exception:
            pass  # Observability must never affect migration/recovery.


def begin(*args,**kwargs): return _call('begin',*args,**kwargs)
def update(**kwargs): return _call('update',**kwargs)
def finish(status='complete; pending commit'): return _call('finish',status)
def log(text): return _call('log',text,important=True)
def pause(): return _call('pause')
def bind(connection,gate): return _call('bind_target',connection,gate)


def stop():
    global _active
    _call('close')
    _active=None


class InputCounter:
    def __init__(self,wrapped):
        self.wrapped,self.bytes=wrapped,0
    def read(self,size=-1):
        data=self.wrapped.read(size)
        self.bytes+=len(data)
        update(bytes_read=self.bytes)
        return data


class OutputCounter:
    def __init__(self,wrapped):
        self.wrapped,self.bytes=wrapped,0
    def write(self,data):
        result=self.wrapped.write(data)
        self.bytes+=len(data.encode('utf-8') if isinstance(data,str) else data)
        update(bytes=self.bytes)
        return result
