from ctypes import alignment
from importlib.resources import read_text
from regex import P
import yaml
from pathlib import Path
from urllib.parse import urlparse, urlunsplit

from pydantic import parse_obj_as, AnyHttpUrl

  
def toyaml(dict):
    return yaml.safe_dump(dict, sort_keys=False, allow_unicode=True)

def from_yaml(yml_path):
    return yaml.safe_load(yml_path.read_text(encoding="utf-8"))


def load_alignments(path):
    alignment = from_yaml(Path(path))
    return alignment

def extract_text(alignment,seg_pair_id):
    seg_pairs = alignment["segment_pairs"]
    seg_srcs = alignment["segment_sources"]
    for seg_id in seg_pairs.keys():
        if seg_id != seg_pair_id:
            continue
        al = seg_pairs[seg_id]
        sources = al.keys()
        for source in sources:
            base_file = seg_srcs[source]["base"]
            seg_id = al[source]

            if seg_id == "None":
                continue

            text = get_text(seg_id,source,base_file)
            print(text)
            print("-----------------------------------------------------------")
        print("*****************************************************************")    

def get_text(seg_id,source,base_file):
    path = f"./root/opfs/{source}/{source}.opf/layers/{base_file}/Segment.yml"
    segment_yml = from_yaml(Path(path))
    span = get_span(segment_yml,seg_id)
    base_path = f"./root/opfs/{source}/{source}.opf/base/{base_file}.txt"
    base_text = Path(base_path).read_text()

    return base_text[span["start"]:span["end"]]


def get_span(segment_yml,seg_id):
    annotations = segment_yml["annotations"]
    span = annotations[seg_id]["span"]
    return span

def main():
    alignment_path = "root/opas/AE92897F9/AE92897F9.opa/55C1.yml"
    seg_id = "bcdb643b4d6c4856901edcac817eedca"
    alignment  = load_alignments(alignment_path)
    extract_text(alignment,seg_id)

def check_span():
    text = Path("root/opfs/I689F5A8D/I689F5A8D.opf/base/4ED2.txt").read_text(encoding="utf-8")
    print(text[8226:10344])

def test_url(url:AnyHttpUrl):
    print(url)

if __name__ == "__main__":
   url=parse_obj_as(AnyHttpUrl, "https://www.test.com")
   