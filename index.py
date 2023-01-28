from pathlib import Path
from uuid import uuid4
from openpecha.core.ids import get_alignment_id,get_base_id
from openpecha.utils import dump_yaml, load_yaml
from datetime import date, datetime


class OsloAlignment:
    def __init__(self,root_path):
        self.root_alignment_path = f"{root_path}/opas"
        self.root_opf_path = f"{root_path}/opfs"

    def create_alignment_yml(self,pechas):
        seg_pairs = self.get_segment_pairs(pechas)
        self.segment_sources = {}
        for pecha in pechas:
            alignment = {
                pecha['pecha_id']:{
                    "type": "origin_type",
                    "relation": "translation",
                    "lang": pecha['lang'],
                    "base":pecha["base_id"]
                }

            }
            self.segment_sources.update(alignment)

        alignments = {
            "segment_sources": self.segment_sources,
            "segment_pairs":seg_pairs
        }    

        return alignments        

    def create_alignment(self,pechas,pecha_name):
        alignment_id = get_alignment_id()
        alignment_to_base={}
        alignment_path = f"{self.root_alignment_path}/{alignment_id}/{alignment_id}.opa"
        alignment = self.create_alignment_yml(pechas)
        base_id = self.write_alignment(alignment_path,alignment)
        for pecha in pechas:
            alignment_to_base.update({f"{pecha['pecha_id']}/{pecha['base_id']}":base_id})
        meta = self.create_alignment_meta(alignment_id,pechas,alignment_to_base,pecha_name)
        readme = self.create_readme_for_opa(alignment_id,pecha_name,pechas)
        dump_yaml(meta,Path(f"{alignment_path}/meta.yml"))
        Path(f"{self.root_alignment_path}/{alignment_id}/readme.md").write_text(readme)

        return alignment_id


    def get_bases(self,pecha):
        volumes = []
        bases = list(Path(f"{self.root_opf_path}/{pecha['pecha_id']}/{pecha['pecha_id']}.opf/base").iterdir())
        for base in bases:
            volumes.append(base.stem)
        return volumes


    def get_segment_pairs(self,pechas):
        seg_pairs = {}
        first_pecha = pechas[0]["pecha_id"]
        len_of_seg = len(self.pecha_id_to_seg_id_list[first_pecha])
        for i in range(len_of_seg):
            seg_id = uuid4().hex
            seg_pair = {}
            for pecha in pechas:
                pecha_id = pecha["pecha_id"]
                seg_ann = self.pecha_id_to_seg_id_list[pecha_id][i]
                if seg_ann != None:
                    seg_pair.update({pecha_id:seg_ann})
            if len(seg_pair)>1:
                seg_pairs.update({seg_id:seg_pair})
        return seg_pairs


    @staticmethod
    def _mkdir(path: Path):
        path.mkdir(parents=True, exist_ok=True)
        return path

    def get_ids(self,annotations):
        final_segments = {}
        num = 1
        for uid, _ in annotations.items():
            final_segments.update({num:uid})
            num += 1
        return final_segments 
   

    def write_alignment(self,alignment_path,alignment):
        base_id = get_base_id()
        alignment_path = Path(f"{alignment_path}")
        self._mkdir(alignment_path)
        dump_yaml(alignment, Path(f"{alignment_path}/{base_id}.yml"))
        return base_id


    def create_alignment_meta(self,alignment_id,pechas,alignment_to_base,pecha_name):
        lang  = list(set([pecha['lang'] for pecha in pechas]))
        pecha_ids = [pecha["pecha_id"] for pecha in pechas]
        metadata = {
            "id": alignment_id,
            "title": pecha_name,
            "type": "translation",
            "pechas":pecha_ids,
            "source_metadata":{
                "languages":lang,
                "datatype":"PlainText",
                "created_at":datetime.now(),
                "last_modified_at":datetime.now()
                },
            "alignment_to_base":alignment_to_base
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

