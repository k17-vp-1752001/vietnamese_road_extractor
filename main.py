from nlp import nlp_extractor
from database import update_database
from server.vncorenlp_server import VNCoreNLPServer


if __name__ == '__main__':
    server = VNCoreNLPServer()
    try:
        server.start()
        nlp_extractor.run()
        update_database.close_connection()
        server.close()
    except KeyboardInterrupt as e:
        server.close()
    # os.system('cmd /k "date"')

