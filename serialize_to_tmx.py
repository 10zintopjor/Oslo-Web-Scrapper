from __future__ import annotations
from xml.etree import ElementTree
from openpecha.utils import dump_yaml, load_yaml
from xml.dom import minidom
from pathlib import Path

def create_body(body,seg_pairs,pecha_lang,volume):
    for seg_id in seg_pairs:
        tu =ElementTree.SubElement(body,'tu',{"seg_id":seg_id})
        for elem in seg_pairs[seg_id]:
            pecha_id = elem
            segment_id = seg_pairs[seg_id][elem]
            text = get_text(pecha_id,segment_id,volume)
            if text!="":
                tuv = ElementTree.SubElement(tu,"tuv",{"lang":pecha_lang[pecha_id]})     
                tuv.text=text


def get_text(pecha_id,seg_id,volume):
    if seg_id == None:
        return "------------"
    else:
        pecha_path = f"./{pecha_id}/{pecha_id}.opf"    
        base_text_path = f"./{pecha_path}/base/{volume}.txt"
        layer_path = f"./{pecha_path}/layers/{volume}/Segment.yml"
        segment_yml = load_yaml(Path(layer_path))
        annotations = segment_yml.get("annotations",{})
        for id in annotations:
            if id == seg_id:
                span = annotations[id]['span']
                base_text = get_base_text(span,base_text_path)
                return base_text


def get_base_text(span,base_text_path):
    base_text = Path(base_text_path).read_text()
    start = span['start']
    end = span['end']

    return base_text[start:end+1]

def create_main(seg_pairs,pecha_lang,volume):
    root = ElementTree.Element('tmx')
    header = ElementTree.SubElement(root,'header')
    body = ElementTree.SubElement(header,'body')
    create_body(body,seg_pairs,pecha_lang,volume)
    tree = prettify(root)
    #tree.write(f"./tmx/{volume}.tmx","UTF-8") 
    Path(f"./tmx/{volume}.tmx").write_text(tree)   

def create_tmx(alignment,volume):
    seg_pairs = alignment['segment_pairs']
    pecha_lang = get_pecha_lang(alignment['segment_sources'])
    create_main(seg_pairs,pecha_lang,volume)

def get_pecha_lang(segment_srcs):
    pecha_lang = {}
    for seg in segment_srcs:
        pecha_lang.update({seg:segment_srcs[seg]['language']})
    
    return pecha_lang


def prettify(elem):
    """Return a pretty-printed XML string for the Element.
    """
    rough_string = ElementTree.tostring(elem, 'utf-8')
    reparsed = minidom.parseString(rough_string)
    return reparsed.toprettyxml(indent="  ")
