import json
import os
from pathlib import Path


def write_result(path,data):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    descriptor=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(descriptor,'w') as target:
        json.dump(data,target,indent=2,default=str)
        target.write('\n')
