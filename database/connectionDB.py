import pymongo
from pymongo.errors import ConnectionFailure


class Database:

    def __init__(self, connection_string):
        self.connection_string = connection_string
        self.client = pymongo.MongoClient(self.connection_string)
        self.database = ''
        print("Client connect successfully")

    def connect_database(self, database_name: str):
        try:
            db = self.client[database_name]
        except ConnectionFailure as e:
            print("Connection Failed")
            return e

        self.database = db
        return db

    def get_collection(self, database_name: str, collection_name: str):
        db = self.connect_database(database_name)
        return db[collection_name]

    def close(self):
        self.client.close()
