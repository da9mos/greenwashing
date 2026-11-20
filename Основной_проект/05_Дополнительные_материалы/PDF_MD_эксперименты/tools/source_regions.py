"""Source-only overlapping views and conservative text-block coverage diagnostics."""
from pathlib import Path
from collections import Counter
import re
from compare_results import cleaned_text

def region_boxes(width,height):
    if width<=0 or height<=0:raise ValueError('Positive page dimensions required')
    return [('top_left',(0,0,width*.56,height*.56)),('top_right',(width*.44,0,width,height*.56)),('bottom_left',(0,height*.44,width*.56,height)),('bottom_right',(width*.44,height*.44,width,height))]

def render_regions(page,output):
    import pymupdf as fitz
    output=Path(output);output.mkdir(parents=True,exist_ok=True);records=[]
    for name,bbox in region_boxes(page.rect.width,page.rect.height):
        rect=fitz.Rect(bbox);scale=min(3.0,2200/max(rect.width,rect.height));p=output/(name+'.png')
        page.get_pixmap(matrix=fitz.Matrix(scale,scale),clip=rect,alpha=False).save(p)
        records.append({'source_region':name,'bbox':list(bbox),'render_scale':scale,'path':str(p)})
    return records

def word_list(text):
    return re.findall(r'[^\W_]+(?:[,.][0-9]+)*',text.casefold().replace('\u00ad',''),re.UNICODE)

def words(text):
    return Counter(word_list(text))

def block_coverage(blocks,markdown):
    output=words(cleaned_text(markdown));records=[]
    for i,block in enumerate(blocks):
        text=block.get('text','');tokens=words(text);total=sum(tokens.values());bad=sum(1 for c in text if c=='\ufffd' or 0xE000<=ord(c)<=0xF8FF or ord(c)<32 and not c.isspace())
        missing=tokens-output;recall=1-sum(missing.values())/total if total else 1
        state='source_text_uncertain' if bad else 'possible_omission' if total>=8 and recall<.70 else 'no_large_omission_detected'
        records.append({'source_id':block.get('source_id','block_'+str(i)),'bbox':block.get('bbox'),'source_tokens':total,'token_recall':round(recall,4),'state':state,'missing_samples':list(missing)[:12],'scope':'Token availability only; not proof of reading order, object relations or correctness'})
    return records

def duplicate_paragraphs(blocks,markdown):
    source=' '.join(' '.join(word_list(b.get('text',''))) for b in blocks)
    paragraphs=Counter(' '.join(word_list(cleaned_text(p))) for p in re.split(r'\n\s*\n',markdown))
    return [{'text_sample':p[:220],'output_occurrences':n,'source_occurrences':source.count(p),'state':'duplicate_text_suspect'}
            for p,n in paragraphs.items() if len(p)>120 and n>1 and source.count(p)==1]
