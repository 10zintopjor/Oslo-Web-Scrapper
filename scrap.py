from os import write
from git import base
from requests.models import Response
from requests_html import HTMLSession
from openpecha.core.ids import get_pecha_id
from datetime import datetime
from openpecha.core.layer import InitialCreationEnum, Layer, LayerEnum, PechaMetaData
from openpecha.core.pecha import OpenPechaFS 
from openpecha.core.annotation import AnnBase, Span
from uuid import uuid4
from index import OsloAlignment
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
            
    
    for pecha in pechas:
        save_meta(pecha_name,pecha)

    obj = OsloAlignment()
    obj.create_alignment(pechas,pecha_name)


def save_meta(pecha_name,pecha):
    opf_path = f"{pecha['pecha_id']}/{pecha['pecha_id']}.opf"
    opf = OpenPechaFS(opf_path=opf_path)
    source_metadata = {
        "id": "",
        "title": pecha_name,
        "language": pecha['lang'],
        "author": "",
    }

    instance_meta = PechaMetaData(
        initial_creation_type=InitialCreationEnum.input,
        created_at=datetime.now(),
        last_modified_at=datetime.now(),
        source_metadata=source_metadata)    

    opf._meta = instance_meta
    opf.save_meta()
    readme=create_readme(pecha['pecha_id'],source_metadata)
    with open(f"{opf_path}/readme.md","w") as f:
        f.write(readme)


def create_readme(pecha_id,source_metadata):
    pecha = f"|Pecha id | {pecha_id}"
    Table = "| --- | --- "
    Title = f"|Title | {source_metadata['title']} "
    lang = f"|Language | {source_metadata['language']}"
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
    texts = ""
    
    response = make_request(pre_url+link.attrs['href'])
    content = response.html.find('div.infofulltekstfelt div.BolkContainer')
    for block in content:
        div = block.find('div.textvar div.Tibetan,div.Chinese,div.English,div.Sanskrit')
        if len(div) != 0:
            base_text = write_file(div,base_text)
    filename = link.text if par_dir == None else f"{par_dir}_{link.text}"
 
    for pecha in pechas:
        create_opf(base_text[pecha['name']],filename,pecha['pecha_id'])


def write_file(divs,base_dic):
    for index,div in enumerate(divs,start=0):
        base_text=""
        base_dic[f"col_{index}"] = [] if f"col_{index}" not in base_dic else base_dic[f"col_{index}"]
        spans = div.find('span')
        for span in spans:
            if len(span.text) != 0:  
                base_text+=change_text_format(span.text)
            else:
                base_text+="--------------"    
        if len(spans) == 1 and len(spans[0].text) == 0:
            pass
        else:
            base_text+="\n\n"
            base_dic[f"col_{index}"].append(base_text)
        
    return base_dic

def change_text_format(text):
    base_text=""
    text = text.replace("\n","") 
    ranges = iter(range(len(text)))
    print(len(text))
    for i in ranges:
        if i<len(text)-1:
            if i%90 == 0 and i != 0 and re.search("\W",text[i+1]):
                base_text+=text[i]+"\n"
            elif i%90 == 0 and i != 0 and re.search("\w",text[i+1]):
                while i < len(text)-1 and re.search("\w",text[i+1]):
                    base_text+=text[i]
                    i = next(ranges) 
                base_text+=text[i]+"\n"    
            else:
                base_text+=text[i]
        else:
            base_text+=text[i]

    return base_text

def create_opf(base_text,filename,pecha_id):
    opf_path = f"{pecha_id}/{pecha_id}.opf"
    opf = OpenPechaFS(opf_path=opf_path)
    layers = {f"{filename}": {LayerEnum.segment: get_segment_layer(base_text)}}
    bases = {f"{filename}":get_base_text(base_text)}
    opf.layers = layers
    opf.base = bases
    opf.save_base()
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