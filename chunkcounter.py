import chromadb

client = chromadb.PersistentClient(path="data/chromaqwen0-6bembedding")

for c in client.list_collections():
    print(c.name, c.count())