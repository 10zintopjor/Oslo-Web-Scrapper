from requests import request
import requests
from requests_html import HTMLSession
from openpecha.core.ids import get_base_id,get_initial_pecha_id
from datetime import datetime
from openpecha.core.layer import Layer, LayerEnum
from openpecha.core.pecha import OpenPechaFS 
from openpecha.core.metadata import InitialPechaMetadata,InitialCreationType
from bs4 import BeautifulSoup

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
import os
import logging
import csv
from tqdm import tqdm

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
        items = []
        response = self.make_request(self.start_url)
        li = response.html.find('ul li a')
        for link in li:
            item = {
            'name' : link.text,
            'ref' : link.attrs['href']
            }
            items.append(item)
        return items

    def parse_page(self,item):
        chapters =[]
        base_texts = []
        response = self.make_request(item)
        coninuous_bar = response.html.find('div.divControlMain div#nav-menu li#nav-2 a',first=True)
        coninuous_bar_href = coninuous_bar.attrs['href']  
        response = requests.get(self.pre_url+coninuous_bar_href)
        soup = BeautifulSoup(response.text,'html.parser')
        nav_bar = soup.select_one('div.venstrefulltekstfelt')
        links = nav_bar.findChildren('table',recursive=False)
        content = soup.select('div.infofulltekstfelt div.BolkContainer')
        if not content:
            return
        cols = content[0].select('div.textvar div.Tibetan,div.Chinese,div.English,div.Sanskrit,div.German,div.Pāli,div.Uighur,div.French,div.Mongolian')
        self.pechas = self.get_pechas(cols)
        self.pecha_name = soup.select_one('div.headline').text
        complete_text_link = ""
        for link in links:
            hrefs = link.select('a')
            for href in hrefs:
                if href.text == "Complete text":
                    complete_text_link = href["href"]
                elif href['href'] == "javascript:;":
                    continue
                else:
                    chapters.append(href.text)                    
                    base_text = self.parse_text_page(href)
                    self.check_base_length(base_text,href.text)
                    base_texts.append(base_text)
        for pecha in self.pechas:
            base_id = get_base_id()
            pecha.update({"base_id":base_id})
            self.create_opf(base_texts,pecha,base_id)
            self.save_source(self.pre_url+complete_text_link,base_id,pecha)  
            self.create_meta(pecha,base_texts,base_id,chapters)
            readme=self.create_readme(pecha['pecha_id'],self.pecha_name,pecha['lang']) 
            Path(f"{self.root_opf_path}/{pecha['pecha_id']}/readme.md").write_text(readme)
        
        return 

    def check_base_length(self,base_text,title):
        set_count = set()
        for col_no,text in base_text.items():
            set_count.add(text.count("\n"))
            
        if len(set_count) > 1:
            print(title)
            for col_no,text in base_text.items():
                print(col_no+"  "+str(text.count("\n")))
        


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
            elif col.attrs["class"][0] == "Uighur":
                lang = "ug"
            elif col.attrs["class"][0] == "French":
                lang = "fr"
            elif col.attrs["class"][0] == "Mongolian":
                lang = "mon"    
            
            pecha_id = {"name":f"col_{index}","pecha_id":get_initial_pecha_id(),"lang":lang}
            pecha_ids.append(pecha_id)
        return pecha_ids

    def parse_text_page(self,link):
        base_text = {}
        response = self.make_request(self.pre_url+link["href"])
        content = response.html.find('div.infofulltekstfelt div.BolkContainer')
        for index,block in enumerate(content):
            div = block.find('div.textvar div.Tibetan,div.Chinese,div.English,div.Sanskrit,div.German,div.Pāli,div.Uighur,div.French,div.Mongolian')
            if len(div) != 0:
                base_text = self.write_file(div,base_text)
        return base_text        
        
        

    def convert_to_uni(self,text):
        obj = Converter()
        converter = pyewts()

        ewts = obj.alacToEwts(text)
        uni =converter.toUnicode(ewts)
        formatted_text = self.change_text_format(uni)
        
        return formatted_text

    def save_source(self,url,base_id,pecha):
        response = self.make_request(url)
        self._mkdir(Path(f"{self.root_opf_path}/{pecha['pecha_id']}/Source"))
        Path(f"{self.root_opf_path}/{pecha['pecha_id']}/Source/{base_id}.html").write_text(response.text.strip())

    def write_file(self,divs,base_dic):
        prev_base_dic = base_dic.copy()
        for index,div in enumerate(divs,start=0):
            base_text=""
            base_dic[f"col_{index}"] = "" if f"col_{index}" not in base_dic else base_dic[f"col_{index}"]
            spans = div.find('span')
            for span in spans:
                if len(span.text) != 0:
                    base_text+=span.text 
            
            if len(spans) == 1 and len(spans[0].text) == 0:
                base_dic[f"col_{index}"]+="\n"
            elif base_text != "":
                if div.attrs["class"][0] == "Tibetan":
                    base_text = self.convert_to_uni(base_text)
                base_text=self.change_text_format(base_text)  
                base_text+="\n"
                base_dic[f"col_{index}"]+=self.remove_noises(base_text)
            elif base_text == "":
                base_dic[f"col_{index}"]+="\n"

        return base_dic
    
    def remove_noises(self,text):
        text = re.sub("\(\d+\)", "", text)
        text = re.sub("༼.*༽", "", text)
        text = re.sub("\|\|\d+\|\|", "", text)
        text = re.sub("\|", "", text)



        return text
        

    @staticmethod
    def change_text_format(text):
        text = text.replace("\n"," ")
        return text

    def create_opf(self,base_text,pecha,base_id):
        pecha_id = pecha["pecha_id"]
        base_text,cleaned_base_text = self.get_base_text(base_text,pecha)
        opf_path = f"{self.root_opf_path}/{pecha_id}/{pecha_id}.opf"
        opf = OpenPechaFS(path =opf_path)
        opf.bases = {base_id:cleaned_base_text}
        if base_text[0] != "Chapter Empty":
            layers = {f"{base_id}": {LayerEnum.segment: self.get_segment_layer(base_text,pecha_id)}}
            opf.layers = layers
            opf.save_layers() 
        opf.save_base()
    
        return base_id
        

    def get_base_text(self,base_texts,pecha):

        text = ""
        col_no = pecha["name"]
        cleaned_text = ""
        for base_text in base_texts:
            clenaed_string = self.remove_consec_duplicates(base_text[col_no]) 
            cleaned_text+=clenaed_string
            
            text+=base_text[col_no]
        
        return text,cleaned_text


    def remove_consec_duplicates(self,s):
        new_s = re.sub("\n\n*","\n",s)

        return new_s[1:] if new_s[0] == "\n" else new_s

    def get_segment_layer(self,base_texts,pecha_id):
        segment_annotations = {}
        char_walker =0
        self.pecha_id_to_seg_id_list[pecha_id] = []
        for base_text in base_texts.splitlines():
            if base_text == "":
                self.pecha_id_to_seg_id_list[pecha_id].append(None)
                continue
            segment_annotation,char_walker,seg_id = self.get_segment_annotation(char_walker,base_text)
            segment_annotations.update(segment_annotation)
            self.pecha_id_to_seg_id_list[pecha_id].append(seg_id)

        segment_layer = Layer(annotation_type= LayerEnum.segment,
        annotations=segment_annotations
        )        

        return segment_layer


    def get_segment_annotation(self,char_walker,base_text):
        seg_id = uuid4().hex
        
        segment_annotation = {
            seg_id:AnnBase(span=Span(start=char_walker, end=char_walker + len(base_text)))
        }

        return (segment_annotation,len(base_text)+1+char_walker,seg_id)

    def get_annotations(self,pecha,base_id,base_texts,chapters):
        prev_end = 0
        annotation = []
        col_no = pecha["name"]
        for base_text,chapter in zip(base_texts,chapters):
            text = base_text[col_no]
            annotation.append({"title":chapter.replace("\n",""),"span":{"start":prev_end,"end":prev_end+len(text)}})
            prev_end+=len(text)
        annotations =  {uuid4().hex:{"base":f"{base_id}.txt","Chapters":annotation}}
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

    def get_base_meta(self,base_id):
        order = 1
        base_meta = {base_id:{
                "title": base_id,
                "base_file": f"{base_id}.txt",
                "order":order
            }}
        order+=1

        return base_meta

    def create_meta(self,pecha,base_texts,base_id,chapters):
        opf_path = f"{self.root_opf_path}/{pecha['pecha_id']}/{pecha['pecha_id']}.opf"
        opf = OpenPechaFS(path=opf_path)
        instance_meta = InitialPechaMetadata(
            id=pecha['pecha_id'],
            source = self.start_url,
            initial_creation_type=InitialCreationType.input,
            source_metadata={
                "title":self.pecha_name,
                "language": pecha['lang']
            })    

        annotations = self.get_annotations(pecha,base_id,base_texts,chapters)
        index = Layer(annotation_type=LayerEnum.index, annotations=annotations)
        opf._meta = instance_meta
        opf._index = index
        opf.save_meta()
        opf.save_index()


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

    
        
    def scrap(self,url,pechas_catalog,alignment_catalog):
        opf_paths = []
        self.pecha_id_to_seg_id_list = {}
        self.parse_page(url)
        if not hasattr(self,"pechas"):
            return
        for pecha in self.pechas:
            #Path(f"{self.root_opf_path}/{pecha['pecha_id']}/readme.md").touch(exist_ok=True)
            #self.publish_opf(f"{self.root_opf_path}/{pecha['pecha_id']}")
            pechas_catalog.info(f"{pecha['pecha_id']},{pecha['lang']},{self.pecha_name},https://github.com/OpenPecha/{pecha['pecha_id']}")
            #opf_paths.append(f"{self.root_opf_path}/{pecha['pecha_id']}")

        alignment_id = self.create_alignment(self.pechas,self.pecha_name)
        alignment_catalog.info(f"{alignment_id},{self.pecha_name},https://github.com/OpenPecha/{alignment_id}")
        self.create_csv(alignment_id)
        opa_path = f"{self.root_alignment_path}/{alignment_id}"
        #tmx_path = self.create_tmx(alignment_vol_map)
        #self.publish_opf(opa_path)
        #self.create_realease(alignment_id,[tmx_path])

    def scrap_all(self):
        bool_try = None
        paths = []
        skip = ["http://www2.hf.uio.no/common/apps/permlink/permlink.php?app=polyglotta&context=volume&uid=b7e8f921-01f7-11e4-a105-001cc4ddf0f4"
        ,"http://www2.hf.uio.no/common/apps/permlink/permlink.php?app=polyglotta&context=volume&uid=405e3a68-e661-11e3-942f-001cc4ddf0f4",
        "http://www2.hf.uio.no/common/apps/permlink/permlink.php?app=polyglotta&context=volume&uid=30400045-e664-11e3-942f-001cc4ddf0f4",
        "http://www2.hf.uio.no/common/apps/permlink/permlink.php?app=polyglotta&context=volume&uid=976155db-e670-11e3-942f-001cc4ddf0f4"]
        pechas_catalog = self.set_up_logger("pechas_catalog")
        alignment_catalog =self.set_up_logger("alignment_catalog")
        err_log = self.set_up_logger('err')
        items = self.get_page()
        for item in tqdm(items):
            if bool_try:
                print(item['ref'])
                if item["ref"] in skip:
                    continue
                elif "http" in item['ref']:
                    path = self.scrap(item['ref'],pechas_catalog,alignment_catalog)
                    paths.append(path)
                else:
                    path = self.scrap(self.pre_url+item['ref'],pechas_catalog,alignment_catalog) 
                    paths.append(path)
                
                
            if item["ref"] == "http://www2.hf.uio.no/common/apps/permlink/permlink.php?app=polyglotta&context=volume&uid=64064ed8-3f39-11e0-8f33-001cc4df1abe":
                bool_try = True
            """ try:
                if "http" in val['ref']:
                    path = self.scrap(val['ref'],pechas_catalog,alignment_catalog)
                    paths.append(path)
                else:
                    self.scrap(self,self.pre_url+val['ref'],pechas_catalog,alignment_catalog) 
            except:
                err_log.info(f"{val['ref']}")
            break """

        return paths


def publish_repo(pecha_path, asset_paths=None):
    github_utils.github_publish(
        pecha_path,
        message="initial commit",
        not_includes=[],
        layers=[],
        org=os.environ.get("OPENPECHA_DATA_GITHUB_ORG"),
        token=os.environ.get("GITHUB_TOKEN")
       )
    if asset_paths:
        repo_name = pecha_path.stem
        #asset_name = asset_path.stem
        #shutil.make_archive(asset_path.parent / asset_name, "zip", asset_path)
        #asset_paths.append(f"{asset_path.parent / asset_name}.zip")
        github_utils.create_release(
            repo_name,
            prerelease=False,
            asset_paths=asset_paths, 
            org=os.environ.get("OPENPECHA_DATA_GITHUB_ORG"),
            token=os.environ.get("GITHUB_TOKEN")
        )
def main():
    obj = OsloScrapper("./root")
    pechas_catalog = obj.set_up_logger("pechas_catalog")
    alignment_catalog =obj.set_up_logger("alignment_catalog")
    url = "http://www2.hf.uio.no/common/apps/permlink/permlink.php?app=polyglotta&context=volume&uid=64064ed8-3f39-11e0-8f33-001cc4df1abe"
    obj.scrap(url,pechas_catalog,alignment_catalog)
    

if __name__ == "__main__":

    main()
    """ obj = OsloScrapper("./root")
    paths = obj.scrap_all()
    for path in paths:
        opf_paths,opa_path,tmx_path,source_path = path
        for opf_path in opf_paths:
            #publish_repo(pecha_path = opf_path,asset_paths=[source_path])
            continue
        #publish_repo(pecha_path = opa_path,asset_paths=[tmx_path]) """
