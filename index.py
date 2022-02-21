from asyncore import read
from ctypes import alignment
from pathlib import Path
from uuid import uuid4
import os
import logging
from openpecha.core.ids import get_alignment_id
from openpecha import config, github_utils
from openpecha.utils import dump_yaml, load_yaml
from copy import deepcopy
import serialize_to_tmx


logging.basicConfig(
    filename="alignment_opf_map.log",
    format="%(levelname)s: %(message)s",
    level=logging.INFO,
)

class OsloAlignment:
    def create_alignment_yml(self,pechas,volume):
        seg_pairs = self.get_segment_pairs(pechas,volume)
        self.segment_sources = {}
        for pecha in pechas:
            alignment = {
                pecha['pecha_id']:{
                    "type": "origin_type",
                    "relation": "translation",
                    "language": pecha['lang'],
                }

            }
            self.segment_sources.update(alignment)

        alignments = {
            "segment_sources": self.segment_sources,
            "segment_pairs":seg_pairs
        }    

        return alignments        

    def create_alignment(self,pechas,pecha_name):
        volumes = self.get_volumes(pechas[0])
        alignment_id = get_alignment_id()
        alignment_path = f"{alignment_id}/{alignment_id}.opa"

        for volume in volumes:
            alignment = self.create_alignment_yml(pechas,volume)
            meta = self.create_alignment_meta(alignment,volume,pechas)
            self.write_alignment_repo(f"./{alignment_path}/{volume}",alignment,meta)
            serialize_to_tmx.create_tmx(alignment,volume)

        readme = self.create_readme_for_opa(alignment_id,pecha_name,pechas)
        with open(f"{alignment_path}/readme.md","w") as f:
            f.write(readme)

        logging.info(f"{alignment_id}:{list(set([pecha['pecha_id'] for pecha in pechas]))}")    

    def get_volumes(self,pecha):
        volumes = []
        paths = list(Path(f"./{pecha['pecha_id']}/{pecha['pecha_id']}.opf/base").iterdir())
        for path in sorted(paths):
            volumes.append(path.stem)
        return volumes

    def get_segment_pairs(self,pechas,volume):
        segments_ids = {}
        segment_length = ""

        for pecha in pechas:
            try:
                pecha_yaml = load_yaml(
                    Path(f"./{pecha['pecha_id']}/{pecha['pecha_id']}.opf/layers/{volume}/Segment.yml")
                )
                ids = self.get_ids(pecha_yaml["annotations"])
                segment_length = len(ids)
                segments_ids[pecha['pecha_id']]= ids
            except:
                segments_ids[pecha['pecha_id']]= None  

        cur_pair = {}
        pair= {}
        seg_pairs = {}
        
        if segment_length == "":
            return seg_pairs

        for num in range(1,segment_length+1):
            for pecha in pechas:
                try:
                    cur_pair[pecha['pecha_id']]=segments_ids[pecha['pecha_id']][num]
                except:
                    cur_pair[pecha['pecha_id']]="None"
            pair[uuid4().hex] = deepcopy(cur_pair)
            seg_pairs.update(pair)

        return seg_pairs


    def get_ids(self,annotations):
        final_segments = {}
        num = 1
        for uid, _ in annotations.items():
            final_segments.update({num:uid})
            num += 1
        return final_segments 

    def path_exist(self,output_path):

        if not os.path.exists(output_path):
            os.makedirs(output_path)    

    def write_alignment_repo(self,alignment_path,alignment,meta=None):
        self.path_exist(alignment_path)
        alignment_yml_path = Path(f"{alignment_path}/Alignment.yml")
        meta_path = Path(f"{alignment_path}/meta.yml")
        dump_yaml(alignment, alignment_yml_path)
        if meta:
            dump_yaml(meta, meta_path)


    def create_alignment_meta(self,alignment,volume,pechas):
        lang  = list(set([pecha['lang'] for pecha in pechas]))

        metadata = {
            "id": alignment['segment_sources'],
            "title": volume,
            "type": "translation",
            "source_metadata":{"language":lang},
        }
        return metadata

    def create_readme_for_opa(self, alignment_id, pecha_name,pechas):
        lang  = list(set([pecha['lang'] for pecha in pechas]))

        type = "translation"
        alignment = f"|Alignment id | {alignment_id}"
        Table = "| --- | --- "
        Title = f"|Title | {pecha_name} "
        type = f"|Type | {type}"
        languages = f"|Languages | {lang}"
        
        readme = f"{alignment}\n{Table}\n{Title}\n{type}\n{languages}"
        return readme


    def publish_pecha(self,pecha_path):
        github_utils.github_publish(
        pecha_path,
        message="initial commit",
        not_includes=[],
        layers=[],
        org="Openpecha",
        token=os.environ.get("GITHUB_TOKEN"),
    )
