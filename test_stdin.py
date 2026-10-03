import subprocess
import time

cmd = r'"D:\ANSYS Inc\ANSYS Student\v261\fluent\ntbin\win64\fluent.exe" 3ddp -t2 -wait'
process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, shell=True)

commands = """
/file/read-case "D:/Trial1_hemisphere_files/dp0/FFF-1/Fluent/FFF-1-Setup-Output.cas.h5"
/exit
yes
"""
print("Sending commands...")
process.stdin.write(commands)
process.stdin.flush()

try:
    stdout, stderr = process.communicate(timeout=60)
    print("STDOUT:", stdout[-500:])
except subprocess.TimeoutExpired:
    print("Timeout!")
    process.kill()

