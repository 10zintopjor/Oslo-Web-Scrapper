from ctypes import alignment
from importlib.resources import read_text
from regex import P
import yaml
from pathlib import Path


  
def toyaml(dict):
    return yaml.safe_dump(dict, sort_keys=False, allow_unicode=True)

def from_yaml(yml_path):
    return yaml.safe_load(yml_path.read_text(encoding="utf-8"))


def load_alignments(path):
    alignment = from_yaml(Path(path))
    return alignment

def extract_text(alignment):
    seg_pairs = alignment["segment_pairs"]
    for seg_id in seg_pairs.keys():
        al = seg_pairs[seg_id]
        sources = al.keys()
        for source in sources:
            seg_id = al[source]
            if seg_id == "None":
                continue
            text = get_text(seg_id,source)
            print(text)
        print("*****************************************************************")    

def get_text(seg_id,source):
    path = f"./root/opfs/{source}/{source}.opf/layers/07FD/Segment.yml"
    segment_yml = from_yaml(Path(path))
    span = get_span(segment_yml,seg_id)
    base_path = f"./root/opfs/{source}/{source}.opf/base/07FD.txt"
    base_text = Path(base_path).read_text()

    return base_text[span["start"]:span["end"]]


def get_span(segment_yml,seg_id):
    annotations = segment_yml["annotations"]
    span = annotations[seg_id]["span"]
    return span

def main():
    alignmnet_path = "root/alignments/A4948ADF9/A4948ADF9.opa/07FD/Alignment.yml"
    alignment  = load_alignments(alignmnet_path)
    extract_text(alignment)
if __name__ == "__main__":
    main()