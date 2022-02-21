from os import write
from requests_html import HTMLSession
from openpecha.core.ids import get_pecha_id,get_work_id
from datetime import datetime
from openpecha.core.layer import InitialCreationEnum, Layer, LayerEnum, PechaMetaData
from openpecha.core.pecha import OpenPechaFS 
from openpecha.core.annotation import AnnBase, Span
from uuid import uuid4
from index import OsloAlignment
from pathlib import Path
import re



start_url = "https://www2.hf.uio.no/polyglotta/index.php?page=library&bid=2"
pre_url = "https://www2.hf.uio.no/"


def make_request(url):
    s=HTMLSession()
    response =s.get(url)
    return response


def get_page():
    response = make_request(start_url)

    li = response.html.find('ul li a')

    for link in li:
        item = {
        'name' : link.text,
        'ref' : link.attrs['href']
        }

        yield item


def parse_page(item):
    response = make_request(item)
    links = response.html.find('div.venstrefelt table a',first=True)
    response = make_request(pre_url+links.attrs['href'])
    coninuous_bar = response.html.find('div.divControlMain li#nav-2 a',first=True)
    coninuous_bar_href = coninuous_bar.attrs['href']  
    response = make_request(pre_url+coninuous_bar_href)
    nav_bar = response.html.find('div.venstrefulltekstfelt table a')
    content = response.html.find('div.infofulltekstfelt div.BolkContainer')
    cols = content[0].find('div.textvar div.Tibetan,div.Chinese,div.English,div.Sanskrit')
    pechas = get_pecha_ids(cols)
    link_iter = iter(nav_bar)
    pecha_name = response.html.find('div.headline',first=True).text
    
    par_dir = None
    prev_dir = ""

    for link in link_iter:
        
        if 'onclick' in link.attrs:
            nxt  = next(link_iter)    
            if nxt.attrs['class'][0] == "ajax_tree0":
                par_dir = None
            elif nxt.attrs['class'][0] == "ajax_tree1":
                par_dir = par_dir.replace(f"_{prev_dir}","") if par_dir != None else par_dir
            par_dir = nxt.text if par_dir == None else f"{par_dir}_{nxt.text}"
            prev_dir = nxt.text
        elif link.text != "Complete text":
            if link.attrs['class'][0] == "ajax_tree0":
                par_dir = None
            parse_final(link,par_dir,pechas)
            
    obj = OsloAlignment()
    for pecha in pechas:
        volumes = obj.get_volumes(pecha)
        opf_path = create_meta_index(pecha_name,pecha,volumes)
        readme=create_readme(pecha['pecha_id'],pecha_name,pecha['lang'])
        with open(f"{opf_path}/readme.md","w") as f:
            f.write(readme)

    obj.create_alignment(pechas,pecha_name)


def create_meta_index(pecha_name,pecha,volumes):
    opf_path = f"{pecha['pecha_id']}/{pecha['pecha_id']}.opf"
    opf = OpenPechaFS(opf_path=opf_path)
    annotations,work_id_vol_map = get_annotations(volumes,opf_path)

    vol_meta=get_vol_meta(work_id_vol_map)
    
    instance_meta = PechaMetaData(
        id=pecha['pecha_id'],
        initial_creation_type=InitialCreationEnum.input,
        created_at=datetime.now(),
        last_modified_at=datetime.now(),
        source_metadata={
            "title":pecha_name,
            "language": pecha['lang'],
            "volumes":vol_meta
        })    

    index = Layer(annotation_type=LayerEnum.index, annotations=annotations)
    opf._meta = instance_meta
    opf._index = index
    opf.save_index()
    opf.save_meta()

    return opf_path


def get_vol_meta(work_id_vol_map):
    meta = {}
    for id in work_id_vol_map:
        meta.update({uuid4().hex:{
            "title":work_id_vol_map[id],
            "base_file": f"{work_id_vol_map[id]}.txt",
            "work_id":id
        }}) 

    return meta
        

def get_annotations(volumes,opf_path):
    annotations={}
    work_id_vol_map={}
    for volume in volumes:
        id = get_work_id()
        work_id_vol_map.update({id:volume})
        span = get_spans(opf_path,volume)
        annotation =  {uuid4().hex:{"work_id": id,"span":span}}
        annotations.update(annotation)
    return annotations,work_id_vol_map


def get_spans(opf_path,volume):
    path = f"{opf_path}/base/{volume}.txt"
    try:
        layer_path = f"{opf_path}/layers/{volume}/Segment.yml"
        Path(layer_path).read_text()
        text = Path(path).read_text()
        end = len(text)
    except:
        end = 0    
    span =  {"vol": volume ,"start": 0, "end": end}

    return span

def create_readme(pecha_id,pecha_name,lang):
    pecha = f"|Pecha id | {pecha_id}"
    Table = "| --- | --- "
    Title = f"|Title | {pecha_name}"
    lang = f"|Language | {lang}"
    readme = f"{pecha}\n{Table}\n{Title}\n{lang}"
    return readme


def get_pecha_ids(cols):
    pecha_ids = [] 
    for index,col in enumerate(cols,start=0):
        pecha_id = {"name":f"col_{index}","pecha_id":get_pecha_id(),"lang":col.attrs["class"][0]}
        pecha_ids.append(pecha_id)
    return pecha_ids


def parse_final(link,par_dir,pechas):
    base_text = {}
    
    response = make_request(pre_url+link.attrs['href'])
    content = response.html.find('div.infofulltekstfelt div.BolkContainer')
    for block in content:
        div = block.find('div.textvar div.Tibetan,div.Chinese,div.English,div.Sanskrit')
        if len(div) != 0:
            base_text = write_file(div,base_text)
    filename = link.text if par_dir == None else f"{par_dir}_{link.text}"
 
    for pecha in pechas:
        if base_text[pecha['name']]:
            create_opf(base_text[pecha['name']],filename,pecha['pecha_id'])
        else:
            create_opf(["Chapter Empty"],filename,pecha['pecha_id'])    


def write_file(divs,base_dic):
    for index,div in enumerate(divs,start=0):
        base_text=""
        base_dic[f"col_{index}"] = [] if f"col_{index}" not in base_dic else base_dic[f"col_{index}"]
        spans = div.find('span')
        for span in spans:
            if len(span.text) != 0:  
                base_text+=change_text_format(span.text)   
        if len(spans) == 1 and len(spans[0].text) == 0:
            pass
        elif base_text != "":
            base_text+="\n\n"
            base_dic[f"col_{index}"].append(base_text)
        
    return base_dic

def change_text_format(text):
    base_text=""
    prev= ""
    text = text.replace("\n","") 
    ranges = iter(range(len(text)))
    for i in ranges:
        if i<len(text)-1:
            if i%90 == 0 and i != 0 and re.search("\s",text[i+1]):
                base_text+=text[i]+"\n"
            elif i%90 == 0 and i != 0 and re.search("\S",text[i+1]):
                while i < len(text)-1 and re.search("\S",text[i+1]):
                    base_text+=text[i]
                    i = next(ranges) 
                base_text+=text[i]+"\n"    
            elif prev == "\n" and re.search("\s",text[i]):
                continue
            else:
                base_text+=text[i]
        else:
            base_text+=text[i]
        prev = base_text[-1]
    return base_text

def create_opf(base_text,filename,pecha_id):
    opf_path = f"{pecha_id}/{pecha_id}.opf"
    opf = OpenPechaFS(opf_path=opf_path)
    bases = {f"{filename}":get_base_text(base_text)}
    opf.base = bases
    opf.save_base()
    if base_text[0] != "Chapter Empty":
        layers = {f"{filename}": {LayerEnum.segment: get_segment_layer(base_text)}}
        opf.layers = layers
        opf.save_layers()
    

def get_base_text(base_texts):
    text = ""
    for base_text in base_texts: 
        if base_text:
            text+=base_text
        text+="\n"
    return text    


def get_segment_layer(base_texts):
    segment_annotations = {}
    char_walker =0
    for base_text in base_texts:
        segment_annotation,end = get_segment_annotation(char_walker,base_text)
        segment_annotations.update(segment_annotation)
        char_walker += end+1

    segment_layer = Layer(annotation_type= LayerEnum.segment,
    annotations=segment_annotations
    )        

    return segment_layer


def get_segment_annotation(char_walker,base_text):
    
    segment_annotation = {
        uuid4().hex:AnnBase(span=Span(start=char_walker, end=char_walker + len(base_text) - 3))
    }

    return (segment_annotation,len(base_text))


if __name__ == "__main__":
    for val in get_page():
        parse_page('https://www2.hf.uio.no/polyglotta/index.php?page=volume&vid=233')  
        break  



#https://www2.hf.uio.no/polyglotta/index.php?page=volume&vid=511

#https://www2.hf.uio.no/polyglotta/index.php?page=volume&vid=1124