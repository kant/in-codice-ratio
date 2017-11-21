import matplotlib.pyplot as plt
from random import sample
import os
import re
import json
import string
import numpy as np
import cv2
import networkx as nx


PATTERN2SYMBOL = json.load(open('abbr_matchings.json'))
MATCHINGS = [re.compile(k) if k!="\\." else re.compile("\.") for k in PATTERN2SYMBOL.keys()]

HIGH_SYMBOLS = ['A','B','b','C','D','d_tall','E','F','f','G','h','k','L','l',\
                'N','O','Q','R','S','T','U','l_stroke',"s_tall",'w','W']
MID_SYMBOLS = ["a","c","d_mid","e",'I',"i",'M',"m","n","o","r",'r_2',"t","u","s_mid",'P','tyronian_note','H','prae','b_semicolon']
LOW_SYMBOLS = ['j',"s_low","g","p",'per','pro',"q",'que','qui','rum','x','y','z','9','dot']
UPPER_SYMBOLS = ['apostrophe','curl']

OLD_SYMBOLS = ['a','b','c','d_mid','d_tall','e','f','g','h','i','l','m','n','o','p','q','r','s_tall','s_mid','s_low','t','u']


def compute_centroid(img):
    image = cv2.bitwise_not(img.copy())/255

    X, Y = np.meshgrid(range(0,image.shape[1]),range(0, image.shape[0]))
    x_coord = int(np.round((X*image).sum() / image.sum().astype("float")))
    y_coord = int(np.round((Y*image).sum() / image.sum().astype("float")))

    return x_coord, y_coord


def generate_word(word, dataset_filenames):
    alt_decomp = [(a.span(),a.re.pattern) for m in MATCHINGS for a in m.finditer(word)]
    alt_graph = nx.DiGraph()

    for (start, end), pattern in alt_decomp:
        alt_graph.add_edge(start, end, label=pattern)

    try:
        node_path = sample(list(nx.all_simple_paths(alt_graph, 0, len(word))), 1)[0]
    except:
        print(word)
        raise
    pattern_seq = [alt_graph.get_edge_data(u,v)['label'] for u, v in zip(node_path, node_path[1:])]

    symbol_seq = []
    for p in pattern_seq:
        patt = sample(PATTERN2SYMBOL[p],1)[0]
        if isinstance(patt, list):
            symbol_seq += patt
        else:
            symbol_seq.append(patt)

    images = []
    for i,c in enumerate(symbol_seq):
        s = sample(dataset_filenames[c], 1)[0]
        img = cv2.imread(s, cv2.IMREAD_GRAYSCALE)

        comp_n, labels, stats, centroids = cv2.connectedComponentsWithStats(cv2.bitwise_not(img))
        stats = sorted(stats, key=lambda s: s[4])

        if c in OLD_SYMBOLS:
            char_x, char_y, char_w, char_h, char_a = stats[-2]
        else:
            conn_comp_stats = stats[:-1]
            char_x = min([ccs[0] for ccs in conn_comp_stats])
            char_y = min([ccs[1] for ccs in conn_comp_stats])
            char_w = max([ccs[0]+ccs[2] for ccs in conn_comp_stats])-char_x
            char_h = max([ccs[1]+ccs[3] for ccs in conn_comp_stats])-char_y

        images.append((c, img[char_y:char_y+char_h,char_x:char_x+char_w]))

    width = np.sum([img.shape[1] for c, img in images])+ len(images)
    height = np.max([img.shape[0] for c, img in images])*2

    midline = int(height/2)

    blank = np.ones((height, width), dtype='uint8')*255

    for i,(c, image) in enumerate(images):
        # compute bounding box for cropped image to find rightmost x
        crop_start = midline-int(image.shape[0]/2)
        crop_end = crop_start + image.shape[0]
        img_crop = blank.copy()[crop_start:crop_end,:]
        _, _, stats, _ = cv2.connectedComponentsWithStats(cv2.bitwise_not(img_crop))
        stats = sorted(stats, key=lambda s: s[4])
        conn_comp_stats = stats[:-1]

        if len(conn_comp_stats) > 0:
            start_x = max([ccs[0]+ccs[2] for ccs in conn_comp_stats])
        else:
            start_x = int(np.sum([im.shape[1] for c, im in images[:i]]))

        if c in MID_SYMBOLS:
            start_y = midline - int(image.shape[0]/2)
        if c in HIGH_SYMBOLS:
            start_y = midline - int((image.shape[0]/2)*1.3)
        if c in LOW_SYMBOLS:
            start_y = midline - int((image.shape[0]/2)*0.7)
        if c in UPPER_SYMBOLS:
            start_y = midline - int((image.shape[0]/2)*2)

        # add random vertical shift
        # y_shift = np.random.randint(-1,2)
        # start_y += y_shift

        end_x = start_x + image.shape[1]
        end_y = start_y + image.shape[0]
        try:
            blank[start_y:end_y,start_x:end_x] = cv2.bitwise_and(blank[start_y:end_y,start_x:end_x], image, mask=image)
        except:
            print(blank[start_y:end_y,start_x:end_x].shape, image.shape)
            raise

    return blank

def generate_lines(text, maxlen, dataset_filenames, dst_folder='synthetic_lines/'):
    """
        text: array of words (str)
        maxlen: maximum width of the line image

        return: a list of text line images
    """
    line_count = 0
    linelen = 0
    text = list(text)
    words_in_line = []
    lines = []

    for i,wordstr in enumerate(text):
        w = generate_word(wordstr, dataset_filenames)
        linelen += w.shape[1]
        words_in_line.append((wordstr, w))
        if linelen > maxlen or i == (len(text)-1): # we have completed a row, generate image
            height = np.max([wil.shape[0] for _,wil in words_in_line])
            width = np.sum([wil.shape[1] for _,wil in words_in_line]) + len(words_in_line)*2
            blankline = np.ones((height, width), dtype='uint8')*255
            start_x = 5
            linestr = ''

            for s, wil in words_in_line:
                end_x = start_x + wil.shape[1]
                start_y = int(height/2 - wil.shape[0]/2)
                end_y = start_y + wil.shape[0]
                blankline[start_y:end_y,start_x:end_x] = cv2.bitwise_and(blankline[start_y:end_y,start_x:end_x], wil)
                start_x += wil.shape[1] #+ np.random.randint(3,7)
                linestr += s+' '

            cv2.imwrite(dst_folder+str(line_count)+'.png',blankline)
            with open(dst_folder+str(line_count)+'.txt', mode='w') as f:
                f.write(linestr+'\n')

            lines.append((linestr, blankline))
            #reset
            line_count += 1
            linelen = 0
            words_in_line = []

    return lines


if __name__ == '__main__':
    dataset_folder = 'character_samples/'
    dest_folder = 'synthetic_lines/'

    dataset_filenames = {char: [dataset_folder+char+'/'+f for f in os.listdir(dataset_folder+char)] for char in os.listdir(dataset_folder)}

    corpus = open('latin.txt')
    text = re.sub(r'[0-9]|\'|"|,|:|;|\(|\)|\[|\]|<|>|!|\?|—|-|†', '', corpus.read().replace('\n',' ').replace('.', ' . '))

    line_imgs = generate_lines(filter(lambda x: len(x)>0,text.split(' ')[1:]),
                               1200, dataset_filenames)
    print('Lines generated:',len(line_imgs))
    #
    # for i,(wordstr, line) in enumerate(line_imgs):
    #     cv2.imwrite(dest_folder+str(i)+'.png',line)
    #     with open(dest_folder+str(i)+'.txt', mode='w') as f:
    #         f.write(wordstr+'\n')