@ECHO OFF
start "" ^
cd D:\Python_home\VnCoreNLP ^&^& ^
venv\Scripts\activate ^&^& ^
python --version ^&^& ^
python main.py ^&^& ^
venv\Scripts\deactivate ^&^& ^
exit

exit