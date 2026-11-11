import os
import subprocess

script_dir = os.path.dirname(os.path.abspath(__file__))

# Full path to your batch file
batch_file = os.path.join(script_dir, 'restart_odoo.bat')
if __name__ == '__main__':
    # Run the batch file as administrator using PowerShell and keep the window open
    subprocess.run([
        'powershell', '-Command',
        f'Start-Process cmd -ArgumentList "/k {batch_file}" -Verb RunAs'
    ], shell=True)
