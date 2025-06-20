from flask import Flask, request, jsonify
from flask_pymongo import PyMongo
from dotenv import load_dotenv
from flasgger import Swagger
from bson.objectid import ObjectId
from flask_cors import CORS
import os

load_dotenv()

app = Flask(__name__)
CORS(app)
app.config["MONGO_URI"] = os.getenv("MONGO_URI", "mongodb://localhost:27017/mydatabase")
mongo = PyMongo(app)

swagger = Swagger(app)

@app.route("/", methods=["GET"])
def home():
    """
    Welcome message
    ---
    responses:
      200:
        description: API is running
    """
    return jsonify({"message": "Flask + MongoDB + Swagger is working!"})

@app.route("/items", methods=["POST"])
def create_item():
    """
    Create a new item
    ---
    parameters:
      - name: body
        in: body
        required: true
        schema:
          id: Item
          required:
            - item_title
            - item_type
          properties:
            item_title:
              type: string
            item_type:
              type: string
    responses:
      201:
        description: Item created
    """
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    inserted = mongo.db.items.insert_one(data)
    return jsonify({"inserted_id": str(inserted.inserted_id)}), 201

@app.route("/items", methods=["GET"])
def list_items():
    """
    List all items
    ---
    responses:
      200:
        description: List of items
    """
    items = list(mongo.db.items.find())
    for item in items:
        item["_id"] = str(item["_id"])
    return jsonify(items)

@app.route("/tags", methods=["POST"])
def create_tag():
    """
        Create a new tags
        ---
        parameters:
          - name: body
            in: body
            required: true
            schema:
              id: Tag
              required:
                - name
              properties:
                name:
                  type: string
        responses:
          201:
            description: tag created
        """
    data = request.get_json()
    if not data:
        return jsonify({"error": "No data provided"}), 400

    inserted = mongo.db.tags.insert_one(data)

    return jsonify({"inserted_id" : str(inserted.inserted_id)}), 200

@app.route("/tags", methods=["GET"])
def list_tags():
    """
        List all tags
        ---
        responses:
          200:
            description: List of tags
        """
    tags = list(mongo.db.tags.find())

    return jsonify(tags)

@app.route("/items/<item_id>/tags", methods=["POST"], strict_slashes=False)
def create_item_tag_association(item_id):
    """
    Associate tag IDs with an item (in a separate collection)
    ---
    parameters:
      - name: item_id
        in: path
        type: string
        required: true
      - name: body
        in: body
        required: true
        schema:
          required:
            - tag_ids
          properties:
            tag_ids:
              type: array
              items:
                type: string
    responses:
      200:
        description: Tags linked to item
      400:
        description: Bad input
      404:
        description: Item or tag(s) not found
    """
    from bson.objectid import ObjectId

    data = request.get_json()
    tag_ids = data.get("tag_ids", [])

    if not isinstance(tag_ids, list) or not tag_ids:
        return jsonify({"error": "tag_ids must be a non-empty list"}), 400

    try:
        item_oid = ObjectId(item_id)
        tag_oids = [ObjectId(tag_id) for tag_id in tag_ids]
    except Exception:
        return jsonify({"error": "Invalid ObjectId in item_id or tag_ids"}), 400

    # Check item exists
    if not mongo.db.items.find_one({"_id": item_oid}):
        return jsonify({"error": "Item not found.."}), 404

    # Check tags exist
    existing_tags = set(doc["_id"] for doc in mongo.db.tags.find({"_id": {"$in": tag_oids}}))
    if len(existing_tags) != len(tag_oids):
        return jsonify({"error": "One or more tag_ids not found"}), 404

    # Upsert into item_tags collection
    mongo.db.item_tags.update_one(
        {"item_id": item_oid},
        {"$addToSet": {"tag_ids": {"$each": tag_oids}}},
        upsert=True
    )

    return jsonify({
        "message": "Tags associated with item",
        "item_id": item_id,
        "tag_ids": [str(tid) for tid in tag_oids]
    }), 200


@app.route("/items/<item_id>/tags", methods=["GET"])
def get_tags_for_item(item_id):
    """
    Get all tags associated with an item
    ---
    parameters:
      - name: item_id
        in: path
        type: string
        required: true
        description: ID of the item
    responses:
      200:
        description: List of tags
      404:
        description: Item or tag mapping not found
    """
    from bson.objectid import ObjectId

    try:
        item_oid = ObjectId(item_id)
    except Exception:
        return jsonify({"error": "Invalid item_id"}), 400

    # Find tag IDs associated with the item
    tag_map = mongo.db.item_tags.find_one({"item_id": item_oid})
    if not tag_map or not tag_map.get("tag_ids"):
        return jsonify([]), 200  # No tags is not an error — return empty list

    tag_ids = tag_map["tag_ids"]

    # Fetch full tag documents
    tags = list(mongo.db.tags.find({"_id": {"$in": tag_ids}}))

    # Convert ObjectId to string for JSON serialization
    for tag in tags:
        tag["_id"] = str(tag["_id"])

    return jsonify(tags), 200


if __name__ == "__main__":
    app.run(debug=True)
