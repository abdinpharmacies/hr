import datetime

def daterange(start_date, end_date, step_days):
    for i in range(int((end_date - start_date).days), 0, step_days * -1):
        yield start_date + datetime.timedelta(i)
