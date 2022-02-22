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
from openpecha import github_utils,config
from zipfile import ZipFile
import serialize_to_tmx
import re


root_path = "./opfs"
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


def int_to_Roman(num):
        val = [
            1000, 900, 500, 400,
            100, 90, 50, 40,
            10, 9, 5, 4,
            1
            ]
        syb = [
            "M", "CM", "D", "CD",
            "C", "XC", "L", "XL",
            "X", "IX", "V", "IV",
            "I"
            ]
        roman_num = ''
        i = 0
        while  num > 0:
            for _ in range(num // val[i]):
                roman_num += syb[i]
                num -= val[i]
            i += 1
        return roman_num


def parse_page(item):
    response = make_request(item)

    coninuous_bar = response.html.find('div.divControlMain div#nav-menu li#nav-2 a',first=True)
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
    prefix= 0
    chapter = set()
    chapter_no_title = {}

    for link in link_iter:       
        if 'onclick' in link.attrs:
            nxt  = next(link_iter)
            if nxt.attrs['class'][0] == "ajax_tree0":
                par_dir = None       
            elif nxt.attrs['class'][0] == "ajax_tree1":
                par_dir = par_dir.replace(f" {prev_dir}","")
                continue 
            par_dir = f"{par_dir} {nxt.text}" if par_dir != None else f"{nxt.text}"
            prev_dir = nxt.text
        elif link.text != "Complete text":
            if link.attrs['class'][0] == "ajax_tree0":
                par_dir = None
                cno = par_dir
            else:
                if par_dir not in chapter:
                    prefix+=1
                    chapter.add(par_dir)
                    chapter_no_title.update({f"C{int_to_Roman(prefix)}":par_dir})
                cno = prefix
                
            parse_text_page(link,cno,pechas)
    return pechas,pecha_name,chapter_no_title   


def create_tmx(alignment_vol_map,tmx_path):
    for map in alignment_vol_map:
        alignment,volume = map   
        serialize_to_tmx.create_tmx(alignment,volume,tmx_path)
    


def create_meta_index(pecha_name,pecha,volumes,chapter_no_title):
    opf_path = f"{root_path}/{pecha['pecha_id']}/{pecha['pecha_id']}.opf"
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
            "volumes":vol_meta,
            "chapter_to_tile":chapter_no_title,
        })    

    index = Layer(annotation_type=LayerEnum.index, annotations=annotations)
    opf._meta = instance_meta
    opf._index = index
    opf.save_index()
    opf.save_meta()


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
        if col.attrs["class"][0] == "Tibetan":
            lang = "bo"
        elif col.attrs["class"][0] == "English":
            lang = "en"
        elif col.attrs["class"][0] == "Chinese":
            lang = "zh"
        elif col.attrs["class"][0] == "Sanskrit":
            lang = "sa"       
        pecha_id = {"name":f"col_{index}","pecha_id":get_pecha_id(),"lang":lang}
        pecha_ids.append(pecha_id)
    return pecha_ids


def parse_text_page(link,par_dir,pechas):
    base_text = {}
    response = make_request(pre_url+link.attrs['href'])
    content = response.html.find('div.infofulltekstfelt div.BolkContainer')
    for block in content:
        div = block.find('div.textvar div.Tibetan,div.Chinese,div.English,div.Sanskrit')
        if len(div) != 0:
            base_text = write_file(div,base_text)
    filename = link.text if par_dir == None else f"C{int_to_Roman(par_dir)}_{link.text}"
 
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
                base_text+=change_text_format(span.text)+"\n"   
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
    opf_path = f"{root_path}/{pecha_id}/{pecha_id}.opf"
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


def publish_opf(id):
    pecha_path = f"{root_path}/{id}"

    github_utils.github_publish(
    pecha_path,
    not_includes=[],
    message="initial commit"
    )  
    print(f"{id} PUBLISHED")

def create_realease(id,zipped_dir):
    assest_path =[f"{zipped_dir}"]
    github_utils.create_release(
    repo_name=id,
    asset_paths=assest_path,
    )
    print(f"Updated asset to {id}")


def create_tmx_zip(tmx_path,pecha_name):
    zip_path = f"{root_path}/{pecha_name}.zip"
    zipObj = ZipFile(zip_path, 'w')
    tmxs = list(Path(f"{tmx_path}").iterdir())
    for tmx in tmxs:
        zipObj.write(tmx)
    return zip_path


def main(url):
    pechas,pecha_name,chapter_no_title = parse_page(url)
    obj = OsloAlignment(root_path)
    for pecha in pechas:
        volumes = obj.get_volumes(pecha)
        create_meta_index(pecha_name,pecha,volumes,chapter_no_title)
        readme=create_readme(pecha['pecha_id'],pecha_name,pecha['lang'])
        Path(f"{root_path}/{pecha['pecha_id']}/readme.md").touch(exist_ok=True)
        Path(f"{root_path}/{pecha['pecha_id']}/readme.md").write_text(readme)
        #publish_opf(pecha['pecha_id'])    

    alignment_vol_map,alignment_id = obj.create_alignment(pechas,pecha_name)
    tmx_path = Path(f"{root_path}/tmx")
    obj._mkdir(tmx_path)
    create_tmx(alignment_vol_map,tmx_path)
    zip_path = create_tmx_zip(tmx_path,pecha_name)
    #publish_opf(alignment_id)
    #create_realease(alignment_id,zip_path)


if __name__ == "__main__":
    i=0
    for val in get_page():
        main('https://www2.hf.uio.no/polyglotta/index.php?page=volume&vid=435')  
        break
        


#https://www2.hf.uio.no/polyglotta/index.php?page=volume&vid=511

#https://www2.hf.uio.no/polyglotta/index.php?page=volume&vid=1124