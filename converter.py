from sqlite3 import converters
from pyewts import pyewts
from pathlib import Path

class Converter:
    replMapAlalcToEwts={}
    replMapDtsToEwts = {}
    replMapEwtsToAlalc={}
    

    def addMapping(self,target,ewts,targetType,toAlalc):
        if targetType == "DTS" or targetType == "BOTH":
            self.replMapDtsToEwts.update({target:ewts})
        if targetType =="ALALC" or targetType == "BOTH":
            self.replMapAlalcToEwts.update({target:ewts})
        if toAlalc == "ALWAYS_ALALC" or toAlalc == "NFD":
            self.replMapEwtsToAlalc.update({ewts:target})

    def __init__(self):
        self.replMapAlalcToEwts.update({"-":" "})
        self.replMapDtsToEwts.update({"-":" "})
        self.addMapping("ś", "sh", "BOTH", "NEVER_ALALC")
        self.addMapping("s\u0301", "sh", "BOTH", "NEVER_ALALC")
        self.addMapping("ṣ", "Sh", "BOTH", "NEVER_ALALC")
        self.addMapping("s\u0323", "Sh", "BOTH", "NEVER_ALALC")
        self.addMapping("ź", "zh", "BOTH", "NEVER_ALALC")
        self.addMapping("z\u0301", "zh", "BOTH", "NEVER_ALALC")
        self.addMapping("ñ", "ny", "BOTH", "NEVER_ALALC")
        self.addMapping("n\u0303", "ny", "BOTH", "NEVER_ALALC")
        self.addMapping("ṅ", "ng", "BOTH", "NEVER_ALALC")
        self.addMapping("n\u0307", "ng", "BOTH", "NEVER_ALALC")
        self.addMapping("ā", "A", "BOTH", "NFC")
        self.addMapping("a\u0304", "A", "BOTH", "NFD")
        self.addMapping("ī", "I", "BOTH", "NFC")
        self.addMapping("i\u0304", "I", "BOTH", "NFD")
        self.addMapping("ū", "U", "BOTH", "NFC")
        self.addMapping("u\u0304", "U", "BOTH", "NFD")
        self.addMapping("ṃ", "M", "BOTH", "NFC")
        self.addMapping("m\u0323", "M", "BOTH", "NFD")
        self.addMapping("ṁ", "~M", "BOTH", "NEVER_ALALC")
        self.addMapping("m\u0307", "~M", "BOTH", "NEVER_ALALC")
        self.addMapping("m\u0310", "~M", "BOTH", "ALWAYS_ALALC") 
        self.addMapping("m\u0901", "~M", "BOTH", "NEVER_ALALC") 
        self.addMapping("m\u0301", "~M`", "BOTH", "NEVER_ALALC") 
        self.addMapping("ṛ", "r-i", "BOTH", "NFC") 
        self.addMapping("r\u0323", "r-i", "BOTH", "NEVER_ALALC")
        self.addMapping("r\u0325", "r-i", "BOTH", "NFD") 
        self.addMapping("ṝ", "r-I", "BOTH", "NFC") 
        self.addMapping("ṛ\u0304", "r-I", "BOTH", "NEVER_ALALC")
        self.addMapping("r\u0323\u0304", "r-I", "BOTH", "NEVER_ALALC")
        self.addMapping("r\u0304\u0323", "r-I", "BOTH", "NEVER_ALALC")
        self.addMapping("r\u0325\u0304", "r-I", "BOTH", "NFD") 
        self.addMapping("r\u0304\u0325", "r-I", "BOTH", "NEVER_ALALC")
        self.addMapping("ḷ", "l-i", "BOTH", "NFC") 
        self.addMapping("l\u0323", "l-i", "BOTH", "NEVER_ALALC")
        self.addMapping("l\u0325", "l-i", "BOTH", "NFD") 
        self.addMapping("ḹ", "l-i", "BOTH", "NFC") 
        self.addMapping("ḷ\u0304", "l-i", "BOTH", "NEVER_ALALC")
        self.addMapping("l\u0323\u0304", "l-i", "BOTH", "NEVER_ALALC")
        self.addMapping("l\u0304\u0323", "l-i", "BOTH", "NEVER_ALALC")
        self.addMapping("l\u0325\u0304", "l-i", "BOTH", "NFD") 
        self.addMapping("l\u0304\u0325", "l-i", "BOTH", "NEVER_ALALC")
        self.addMapping("ṭ", "T", "BOTH", "NFC")
        self.addMapping("t\u0323", "T", "BOTH", "NFD")
        self.addMapping("ḍ", "D", "BOTH", "NFC")
        self.addMapping("d\u0323", "D", "BOTH", "NFD")
        self.addMapping("ṇ", "N", "BOTH", "NFC")
        self.addMapping("n\u0323", "N", "BOTH", "NFD")
        self.addMapping("`", "&", "BOTH", "ALWAYS_ALALC") 
        self.addMapping("gʹy", "g.y", "BOTH", "ALWAYS_ALALC") 
        self.addMapping("ʹ", "+", "BOTH", "NEVER_ALALC")
        self.addMapping("’", "'", "BOTH", "NEVER_ALALC") 
        self.addMapping("‘", "'", "BOTH", "NEVER_ALALC") 
        self.addMapping("ʼ", "'", "BOTH", "ALWAYS_ALALC") 
        self.addMapping("ʾ", "'", "BOTH", "NEVER_ALALC") 
        self.addMapping("ḥ", "H", "ALALC", "NFC") 
        self.addMapping("h\u0323", "H", "ALALC", "NFD")
        self.addMapping("ḥ", "'", "DTS", "NEVER_ALALC") 
        self.addMapping("h\u0323", "'", "DTS", "NEVER_ALALC")
        
        self.replMapDtsToEwts.update({"š":"sh"})
        self.replMapDtsToEwts.update({"s\u030C":"sh"})
        self.replMapDtsToEwts.update({"ž":"zh"})
        self.replMapDtsToEwts.update({"z\u030C":"zh"})

        self.baseDts = list(self.replMapDtsToEwts.keys())
        self.replDtsToEwts = list(self.replMapDtsToEwts.values())
        self.baseAlalc = list(self.replMapAlalcToEwts.keys())
        self.replAlalcToEwts = list(self.replMapAlalcToEwts.values())
        self.replMapEwtsToAlalc.update({"<<":"\""})
        self.replMapEwtsToAlalc.update({">>":"\""})
        self.replMapEwtsToAlalc.update({"_":" "})
        self.replMapEwtsToAlalc.update({"n+y":"nʹy"})
        self.replMapEwtsToAlalc.update({"t+s":"tʹs"})
        self.replMapEwtsToAlalc.update({"s+h":"sʹh"})
        self.replMapEwtsToAlalc.update({"n+g":"nʹg"})
        self.baseEwts = list(self.replMapEwtsToAlalc.keys())
        self.replEwtsToAlalc = list(self.replMapEwtsToAlalc.values())



    def alacToEwts(self,alalcString):
        alacStr = alalcString.lower()
        new_str = ""
        for char in alacStr:
            if char in self.replMapAlalcToEwts.keys():
                new_str += self.replMapAlalcToEwts[char]
            else:
                new_str+=char    
                
        """ for key in self.replMapAlalcToEwts.keys():
            alacStr.replace(key,self.replMapAlalcToEwts[key]) """
        return new_str


if __name__ == "__main__":
    obj = Converter()
    converter = pyewts()
    text = Path("./test.txt").read_text()
    ewts = obj.alacToEwts(text)
    uni = converter.toUnicode(ewts)