import json
from labelguard import store
from labelguard.corpus import build_index

print(json.dumps(build_index(), indent=2))
store.init_db()
print("Corpus and durable state ready")
