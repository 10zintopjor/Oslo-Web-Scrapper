from lib2to3.pgen2 import token
import os
from index import OsloAlignment
obj = OsloAlignment()
os.environ['GITHUB_TOKEN'] = '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'
path = "./PE4BF344C/PE4BF344C.opf"

obj.publish_pecha(path)