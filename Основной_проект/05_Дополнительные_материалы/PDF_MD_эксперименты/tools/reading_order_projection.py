"""Reversible geometry projection of intact native HTML objects, not semantic approval."""
from __future__ import annotations
import hashlib,re,statistics
BLOCK=re.compile(r'<p>.*?</p>|<table>.*?</table>',re.S)
def project_native_prefix(prefix,objects):
    matches=list(BLOCK.finditer(prefix))
    if not matches or BLOCK.sub('',prefix).strip():raise ValueError('Unexpected native object markup')
    if len(matches)!=len(objects):raise ValueError('Object/markup count mismatch')
    items=[]
    for i,(m,o) in enumerate(zip(matches,objects)):
        if not m[0].startswith('<'+('table' if o['kind']=='table' else 'p')+'>'):raise ValueError('Object kind mismatch')
        items.append({**o,'index':i})
    # The old 12pt threshold misses genuine narrow column gutters. Scale only
    # horizontal gutters to text height; retain original 12pt vertical cuts.
    heights=[o['bbox'][3]-o['bbox'][1] for o in items if o['kind']=='text' and 0<o['bbox'][3]-o['bbox'][1]<40]
    gutter=max(1,min(12,.4*statistics.median(heights))) if heights else 12
    cuts=[]
    def order(group):
        if len(group)<2:return group
        for axis in (0,1):
            ranges=sorted((o['bbox'][axis],o['bbox'][axis+2])for o in group);end=ranges[0][1];gaps=[]
            for left,right in ranges[1:]:
                if left-end>(gutter if axis==0 else 12):gaps.append((left-end,(left+end)/2))
                end=max(end,right)
            if not gaps:continue
            width,cut=max(gaps);before=[o for o in group if o['bbox'][axis+2]<=cut];after=[o for o in group if o['bbox'][axis]>=cut]
            if before and after and len(before)+len(after)==len(group):
                if axis==0 and width<=12:cuts.append({'axis':'x','gap_pt':width,'cut_pt':cut,'objects':[o['index']for o in group]})
                return order(before)+order(after)
        return sorted(group,key=lambda o:(round(o['bbox'][1]/3),o['bbox'][0]))
    indices=[o['index']for o in order(items)]
    if indices==list(range(len(items))):return prefix,None
    # Whitespace separators are retained at their original positions, while only
    # whole original object strings move. The inverse must reproduce every byte.
    slots=[];end=0
    for m in matches:slots.append(prefix[end:m.start()]);end=m.end()
    tail=prefix[end:];blocks=[m[0]for m in matches]
    projected=''.join(slots[i]+blocks[j]for i,j in enumerate(indices))+tail
    inverse=[indices.index(i)for i in range(len(indices))]
    result_matches=list(BLOCK.finditer(projected));back=''.join(slots[i]+result_matches[inverse[i]][0]for i in range(len(indices)))+tail
    if back!=prefix:raise ValueError('Inverse projection failed')
    if sorted(hashlib.sha256(x.encode()).hexdigest()for x in blocks)!=sorted(hashlib.sha256(m[0].encode()).hexdigest()for m in result_matches):raise ValueError('Object changed')
    return projected,{'kind':'source_geometry_reading_order','algorithm':'recursive_xy_cut_scaled_horizontal_gutter','horizontal_gutter_pt':gutter,'permutation':indices,'inverse_permutation':inverse,'narrow_gutter_cuts':cuts,'input_sha256':hashlib.sha256(prefix.encode()).hexdigest(),'output_sha256':hashlib.sha256(projected.encode()).hexdigest(),'all_object_bytes_preserved':True,'inverse_exact':True,'semantic_source_review_completed':False}
