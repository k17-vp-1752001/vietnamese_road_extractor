import dotenv
import os

# from .connectionDB import Database
# from .geocoding_process import geocoding_process
from .connectionDB import Database
from .geocoding_process import geocoding_process

dotenv.load_dotenv()
api_db_conn_str = os.getenv("API_DB_CONNECTION_STRING")
api_db = Database(api_db_conn_str)

be_db_conn_str = os.getenv("BE_DB_CONNECTION_STRING")
be_db = Database(be_db_conn_str)


def close_connection():
    api_db.close()
    be_db.close()


def get_undone_article_list():
    article_collection = api_db.get_collection("PropTech", "articles")
    article_list = list(article_collection.find({"done": False}))
    return article_list


def update(article, road_list):
    update_location_db(road_list)
    api_db.get_collection("PropTech", "articles").update_one(
        {"_id": article.get("_id")},
        {
            "$set": {"done": True}
        },
        upsert=False
    )


def update_location_db(road_list):
    env_coll = api_db.get_collection("PropTech", "environments")
    area_coll = be_db.get_collection("NODE_DB", "areas")
    for road in road_list:
        if road:
            area_document = area_coll.find_one({'fullAddress': road.strip()})
            if area_document:
                remove_keys_list = ['_id', 'createdAt', 'updatedAt', '__v', 'border', 'type']
                area_document['type'] = u'Ngập'
                remove_keys_from_dict(remove_keys_list, area_document)
                doc = env_coll.find_one(area_document)

                if doc is None:
                    area_document.update({"count": 1})
                    location = geocoding_process(area_document)
                    if location is not None:
                        area_document.update({"lat": location["lat"],
                                              "long": location["lon"]}
                                             )
                    env_coll.insert_one(area_document)
                else:
                    env_coll.update_one(area_document,
                                        {
                                            '$inc': {'count': 1},
                                        },
                                        upsert=True)
    pass


def remove_keys_from_dict(keys_list: list, the_dict: dict):
    for key in keys_list:
        the_dict.pop(key, None)
