// mongo-init.js
db = db.getSiblingDB("mongodb"); 

// Drop collection if it exists
db.mycollection.drop();

// Import JSON file using the correct fs module for mongosh
const fileContent = fs.readFileSync('/docker-entrypoint-initdb.d/dados.json', 'utf8');
const documents = JSON.parse(fileContent);

if (Array.isArray(documents) && documents.length > 0) {
    db.mycollection.insertMany(documents);
    print("Successfully imported data!");
} else {
    print("Error: JSON is empty or not an array.");
}