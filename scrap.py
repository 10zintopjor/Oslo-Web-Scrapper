from email.mime import base
from lib2to3.pytree import convert
from os import write
from requests_html import HTMLSession
from openpecha.core.ids import get_pecha_id,get_work_id,get_base_id
from datetime import datetime
from openpecha.core.layer import InitialCreationEnum, Layer, LayerEnum, PechaMetaData
from openpecha.core.pecha import OpenPechaFS 
from openpecha.core.annotation import AnnBase, Span
from uuid import uuid4
from index import OsloAlignment
from pathlib import Path
from openpecha import github_utils,config
from zipfile import ZipFile
from serialize_to_tmx import Tmx
from converter import Converter
from pyewts import pyewts
import re
import logging
import csv

class OsloScrapper(OsloAlignment):
    start_url = "https://www2.hf.uio.no/polyglotta/index.php?page=library&bid=2"
    pre_url = "https://www2.hf.uio.no"

    def __init__(self,root_path):
        self.root_opf_path = f"{root_path}/opfs"
        self.root_tmx_path = f"{root_path}/tmx"
        self.root_tmx_zip_path = f"{root_path}/tmxZip"
        self.source_path = f"{root_path}/sourceFile"

        super().__init__(root_path)


    @staticmethod
    def make_request(url):
        s=HTMLSession()
        response =s.get(url)
        return response


    @staticmethod
    def int_to_roman(num):
        val = [1000, 900, 500, 400,
        100, 90, 50, 40,
        10, 9, 5, 4,1
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

    def get_page(self):
        response = self.make_request(self.start_url)
        li = response.html.find('ul li a')
        for link in li:
            item = {
            'name' : link.text,
            'ref' : link.attrs['href']
            }
            yield item  

    def parse_page(self,item):
        response = self.make_request(item)
        coninuous_bar = response.html.find('div.divControlMain div#nav-menu li#nav-2 a',first=True)
        coninuous_bar_href = coninuous_bar.attrs['href']  
        response = self.make_request(self.pre_url+coninuous_bar_href)
        nav_bar = response.html.find('div.venstrefulltekstfelt table a')
        content = response.html.find('div.infofulltekstfelt div.BolkContainer')
        cols = content[0].find('div.textvar div.Tibetan,div.Chinese,div.English,div.Sanskrit,div.German,div.Pāli,div.Gāndhārī,div.Uighur,div.French')
        self.pechas = self.get_pechas(cols)
        link_iter = iter(nav_bar)
        self.pecha_name = response.html.find('div.headline',first=True).text
        chapter_to_title,base_id_title_maps = self.parse_links(link_iter)
        return chapter_to_title,base_id_title_maps 

    def parse_links(self,link_iter):
        par_dir = None
        prev_dir = ""
        prefix= 0
        chapter = set()
        chapter_no_title = {}
        base_id_title_maps = {}
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
                        chapter_no_title.update({f"C{self.int_to_roman(prefix)}":par_dir})
                    cno = prefix    
                base_id_title_map = self.parse_text_page(link,cno)
                base_id_title_maps.update(base_id_title_map)
        return chapter_no_title,base_id_title_maps

    @staticmethod
    def get_pechas(cols):
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
            elif col.attrs["class"][0] == "German":
                lang = "de"
            elif col.attrs["class"][0] == "Pāli":
                lang = "pi"
            elif col.attrs["class"][0] == "Gāndhārī":
                lang = "pgd"
            elif col.attrs["class"][0] == "Uighur":
                lang = "ug"
            elif col.attrs["class"][0] == "French":
                lang = "fr"
            
            pecha_id = {"name":f"col_{index}","pecha_id":get_pecha_id(),"lang":lang}
            pecha_ids.append(pecha_id)
        return pecha_ids

    def parse_text_page(self,link,par_dir):
        base_text = {}
        base_id = "f"+get_base_id()
        response = self.make_request(self.pre_url+link.attrs['href'])
        content = response.html.find('div.infofulltekstfelt div.BolkContainer')
        self._mkdir(Path(f"{self.source_path}/{self.pecha_name}"))
        for block in content:
            div = block.find('div.textvar div.Tibetan,div.Chinese,div.English,div.Sanskrit,div.German,div.Pāli,div.Gāndhārī,div.Uighur,div.French')
            if len(div) != 0:
                base_text = self.write_file(div,base_text)
        title = link.text if par_dir == None else f"C{self.int_to_roman(par_dir)}_{link.text}"
        if title == "":
            title = "Complete text" 
        for pecha in self.pechas:
            if base_text[pecha['name']]:
                if pecha['lang'] == "bo":
                    bases = self.convert_to_uni(base_text[pecha['name']])
                    self.create_opf(bases,base_id,pecha['pecha_id'])
                else:    
                    self.create_opf(base_text[pecha['name']],base_id,pecha['pecha_id'])
            else:
                self.create_opf(["Chapter Empty"],base_id,pecha['pecha_id']) 
        self.save_source(self.pre_url+link.attrs['href'],title)
        return {base_id:title}

    def convert_to_uni(self,bases):
        obj = Converter()
        converter = pyewts()

        new_bases = []
        for base in bases:
            ewts = obj.alacToEwts(base)
            uni =converter.toUnicode(ewts)
            new_bases.append(uni)
        
        return new_bases

    def save_source(self,url,title):
        response = self.make_request(url)
        self._mkdir(Path(self.source_path))
        with open(f"{self.source_path}/{self.pecha_name}/{title}.html","w") as file:
            file.write(response.text.strip())

    def write_file(self,divs,base_dic):
        for index,div in enumerate(divs,start=0):
            base_text=""
            base_dic[f"col_{index}"] = [] if f"col_{index}" not in base_dic else base_dic[f"col_{index}"]
            spans = div.find('span')
            for span in spans:
                if len(span.text) != 0:
                    base_text+=span.text 
            if len(spans) == 1 and len(spans[0].text) == 0:
                pass
            elif base_text != "":
                base_text=self.change_text_format(base_text)  
                base_text+="\n"if base_text[-1] != "\n" else ""
                base_dic[f"col_{index}"].append(base_text)
        return base_dic
    
    @staticmethod
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


    def create_opf(self,base_text,filename,pecha_id):
        opf_path = f"{self.root_opf_path}/{pecha_id}/{pecha_id}.opf"
        
        opf = OpenPechaFS(path =opf_path)
        bases = {f"{filename}":self.get_base_text(base_text)}
        opf.base = bases
        opf.save_base()
        if base_text[0] != "Chapter Empty":
            layers = {f"{filename}": {LayerEnum.segment: self.get_segment_layer(base_text)}}
            opf.layers = layers
            opf.save_layers() 
            


    def get_base_text(self,base_texts):
        text = ""
        for base_text in base_texts: 
            if base_text:
                text+=base_text
            text+="\n"
        return text              
    
    def get_segment_layer(self,base_texts):
        segment_annotations = {}
        char_walker =0
        for base_text in base_texts:
            segment_annotation,end = self.get_segment_annotation(char_walker,base_text)
            segment_annotations.update(segment_annotation)
            char_walker += end+1

        segment_layer = Layer(annotation_type= LayerEnum.segment,
        annotations=segment_annotations
        )        

        return segment_layer


    def get_segment_annotation(self,char_walker,base_text):
        
        segment_annotation = {
            uuid4().hex:AnnBase(span=Span(start=char_walker, end=char_walker + len(base_text) - 2))
        }

        return (segment_annotation,len(base_text))

    def get_annotations(self,bases,opf_path):
        annotations={}
        for base in bases:
            span = self.get_spans(opf_path,base)
            annotation =  {uuid4().hex:{"base":f"{base}.txt","span":span}}
            annotations.update(annotation)

        return annotations

    def get_spans(self,opf_path,base):
        path = f"{opf_path}/base/{base}.txt"
        try:
            layer_path = f"{opf_path}/layers/{base}/Segment.yml"
            Path(layer_path).read_text()
            text = Path(path).read_text()
            end = len(text)
        except:
            end = 0    
        span =  {"start": 0, "end": end}

        return span   

    def get_base_meta(self,base_id_title_maps):
        base_meta = {}
        order = 1
        for id in base_id_title_maps.keys():
            base_meta.update({id:{
                "title":base_id_title_maps[id],
                "base_file": f"{id}.txt",
                "order":order
            }}) 
            order+=1

        return base_meta

    def create_meta_index(self,pecha,bases,chapter_no_title,base_id_title_maps):
        opf_path = f"{self.root_opf_path}/{pecha['pecha_id']}/{pecha['pecha_id']}.opf"
        opf = OpenPechaFS(path=opf_path)
        annotations = self.get_annotations(bases,opf_path)
        base_meta=self.get_base_meta(base_id_title_maps)
        
        instance_meta = PechaMetaData(
            id=pecha['pecha_id'],
            source = self.start_url,
            initial_creation_type=InitialCreationEnum.input,
            source_metadata={
                "title":self.pecha_name,
                "language": pecha['lang'],
                "base":base_meta,
                "chapter_to_tile":chapter_no_title,
            })    

        index = Layer(annotation_type=LayerEnum.index, annotations=annotations)
        opf._meta = instance_meta
        opf._index = index
        opf.save_index()
        opf.save_meta()

    def create_readme(self,pecha_id,pecha_name,lang):
        pecha = f"|Pecha id | {pecha_id}"
        Table = "| --- | --- "
        Title = f"|Title | {pecha_name}"
        lang = f"|Language | {lang}"
        readme = f"{pecha}\n{Table}\n{Title}\n{lang}"
        return readme 

    @staticmethod
    def set_up_logger(logger_name):
        logger = logging.getLogger(logger_name)
        formatter = logging.Formatter("%(message)s")
        fileHandler = logging.FileHandler(f"{logger_name}.log")
        fileHandler.setFormatter(formatter)
        logger.setLevel(logging.INFO)
        logger.addHandler(fileHandler)

        return logger


    def create_csv(self,alignment_id):
        filename = ""
        for i,pecha in enumerate(self.pechas):
            filename+=pecha['lang']
            if len(self.pechas) > i+1:
                filename+='-'
        with open(f"{self.root_alignment_path}/{alignment_id}/{filename}.csv",'w') as f:
            writer = csv.writer(f)
            writer.writerow(["pecha id","language","url"])
            for pecha in self.pechas:
                lang = pecha['lang']
                pechaid = pecha['pecha_id']
                url = f"https://github.com/OpenPecha/{pechaid}"
                writer.writerow([pechaid,lang,url])


    def create_tmx(self,alignment_vol_map):
        tmxObj = Tmx(self.root_opf_path,self.root_tmx_path)
        tmx_path = f"{self.root_tmx_path}/{self.pecha_name}"
        self._mkdir(Path(tmx_path))
        for map in alignment_vol_map:
            alignment,volume = map   
            tmxObj.create_tmx(alignment,volume,tmx_path)
        zip_path = self.create_tmx_zip(tmx_path)
        return zip_path


    def create_tmx_zip(self,tmx_path):
        zip_path = f"{self.root_tmx_path}/{self.pecha_name}_tmx.zip"
        zipObj = ZipFile(zip_path, 'w')
        tmxs = list(Path(f"{tmx_path}").iterdir())
        for tmx in tmxs:
            zipObj.write(tmx)
        return zip_path    

    def create_sourceFile_zip(self,path):
        zip_path = f"{self.source_path}/{self.pecha_name}_html.zip"
        zipObj = ZipFile(zip_path,'w')
        srcFiles = list(Path(f"{path}").iterdir())
        for file in srcFiles:
            zipObj.write(file)
        return zip_path

    def scrap(self,url):
        opf_paths = []
        pechas_catalog = self.set_up_logger("pechas_catalog")
        alignment_catalog =self.set_up_logger("alignment_catalog")
        chapter_to_title,base_id_title_maps = self.parse_page(url)
        for pecha in self.pechas:
            bases = self.get_bases(pecha)
            self.create_meta_index(pecha,bases,chapter_to_title,base_id_title_maps)
            readme=self.create_readme(pecha['pecha_id'],self.pecha_name,pecha['lang'])
            Path(f"{self.root_opf_path}/{pecha['pecha_id']}/readme.md").touch(exist_ok=True)
            Path(f"{self.root_opf_path}/{pecha['pecha_id']}/readme.md").write_text(readme)
            pechas_catalog.info(f"{pecha['pecha_id']},{pecha['lang']},{self.pecha_name},https://github.com/OpenPecha/{pecha['pecha_id']}")
            opf_paths.append(f"{self.root_opf_path}/{pecha['pecha_id']}")

        alignment_vol_map,alignment_id = self.create_alignment(self.pechas,self.pecha_name)
        alignment_catalog.info(f"{alignment_id},{self.pecha_name},https://github.com/OpenPecha/{alignment_id}")
        self.create_csv(alignment_id)
        opa_path = f"{self.root_alignment_path}/{alignment_id}"
        tmx_path = self.create_tmx(alignment_vol_map)
        src_path = f"{self.source_path}/{self.pecha_name}"
        self._mkdir(Path(src_path))
        source_path =self.create_sourceFile_zip(src_path)
        
        return [opf_paths,opa_path,tmx_path,source_path]

    def scrap_all(self):
        paths = []
        err_log = self.set_up_logger('err')
        for val in self.get_page():
            path = self.scrap("https://www2.hf.uio.no/polyglotta/index.php?page=volume&vid=1020")
            paths.append(path)
            """ try:
                if "http" in val['ref']:
                    print(val["ref"])
                    self.scrap(val['ref'])
                else:
                    self.main(self,self.pre_url+val['ref']) 
            except:
                err_log.info(f"{val}") """
            break   
        return paths

def publish_opf(path):
    github_utils.github_publish(
    path,
    not_includes=[],
    message="initial commit",
    )  
    print(f"{path} PUBLISHED")

def create_realease(id,paths):
    github_utils.create_release(
    repo_name=id,
    asset_paths=paths
    )
    print(f"Updated asset to {id}")

if __name__ == "__main__":
    obj = OsloScrapper("./root")
    paths = obj.scrap_all()
    """ for path in paths:
        opf_paths,opa_path,tmx_path,source_path = path
        for opf_path in opf_paths:
            publish_opf(opf_path)
        publish_opf(opa_path)
        create_realease(Path(opa_path).stem,[tmx_path,source_path])     """
