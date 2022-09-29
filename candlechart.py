import pandas as pd, numpy as np
import math, time

from rich.panel import Panel
from rich.console import Console


console = Console()


class CandleChart:
    def __init__(self,df,heightrownum=32) -> None:
        
        def isCorrect(df):
            for i in df.index:
                if df.loc[i]['h']<df.loc[i]['o'] or df.loc[i]['h']<df.loc[i]['c'] or df.loc[i]['l']>df.loc[i]['o'] or df.loc[i]['l']>df.loc[i]['c']:
                    return False
            return True
        
        if isCorrect(df):
            # self.df =df
            self.df = df.assign(vp=lambda x: np.floor(np.log2(x.h))+x.v)
        else:
            self.df = None
            return
        # height row num
        self.hrn = heightrownum
        self.hmax=self.df.max()['h']
        self.lmin=self.df.min()['l']
        self.hldif = self.hmax - self.lmin
        # single row height points
        self.hrp = math.ceil(self.hldif/self.hrn)
        # total height points
        self.thp = self.hrn*self.hrp
        self.upperline = self.hmax + math.ceil((self.thp-self.hldif)/2)
        self.lowerline = self.lmin - math.floor((self.thp-self.hldif)/2)
        
        self.gdf = pd.DataFrame(data=np.zeros((self.hrn,len(self.df)),dtype=int))

        def fill():
            for i in self.gdf.index:
                #updist and lowdist are same beacase they are the positions pointing to same location
                updist = lambda : self.upperline - self.hrp*(i+1)
                lodist = lambda : self.lowerline + self.hrp*(self.hrn-i-1)
                for c in self.gdf.columns:
                    # self.gdf.loc[i][c]=(self.upperline - self.df['h'][c])//self.hrp
                    if updist() > self.df['h'][c] or lodist() < self.df['l'][c]:
                        self.gdf.loc[i][c] = 0
                    elif self.df['h'][c] - updist() < self.hrp:
                        self.gdf.loc[i][c] = - math.ceil(4*(self.df['h'][c] - updist())/self.hrp)
                        # print(f"{i} {c} {self.df['h'][c]} {self.gdf.loc[i][c]} {4*(self.df['h'][c] - updist())/self.hrp}")
                    elif lodist() - self.df['l'][c] < self.hrp:
                        self.gdf.loc[i][c] = math.floor(4*(lodist() - self.df['l'][c])/self.hrp)
                        # print(f"--{i} {c} {self.df['l'][c]} {self.gdf.loc[i][c]} {4*(lodist() - self.df['l'][c])/self.hrp}")
                    elif updist() < self.df['h'][c] and lodist() > self.df['l'][c]:
                        self.gdf.loc[i][c] = 4
                    # if updist() < self.df['m'][c] and lodist() > self.df['m'][c]-33:
                    #     self.gdf.loc[i][c] = 5
        fill()

    def displayData(self):
        print(f'hrn {self.hrn}, hrp {self.hrp}, ul {self.upperline}, ll {self.lowerline}')
    def getline(self,squeeze=True):
        def colorrgb(vp):
            if vp <= 10:
                return 'rgb(255,0,0)'
            elif vp > 35:
                return 'rgb(0,255,0)'
            else:
                d = int(vp-10)
                return f'rgb({255-d*10},{d*10},0)'
        t1 = time.time()
        vlmin = pow(2,self.df['v'].min())
        vlmax = pow(2,self.df['v'].max())
        vlrange = vlmax-vlmin
        start = self.gdf.columns.start
        stop = self.gdf.columns.stop
        step = 2 if squeeze else 1
        # console.print(f'{self.upperline/20:7.2f}')
        # console.print(f'{"":>7s}', end='')
        row=chr(0x2800)
        for c in range(start,stop-5,step):
            row+='⣀'
        row='[steel_blue]'+row+'[/steel_blue]'
        row+=f'{self.upperline/20:8.2f}'
        yield row
        # console.print()
        for i in self.gdf.index:
            # console.print(f'[steel_blue]{"⢸":>7s}[/steel_blue]', end='')
            row='[steel_blue]⢸[/steel_blue]'
            if not squeeze:
                for c in self.gdf.columns:
                    match self.gdf.loc[i][c]:
                        case 0: v = '⠀'
                        case 1: v = '⠉'
                        case 2: v = '⠛'
                        case 3: v = '⠿'
                        case 4 | -4: v = '⣿'
                        case -1: v = '⣀'
                        case -2: v = '⣤'
                        case -3: v = '⣶'
                        case 5: v='x'
                    console.print(f'{v}', end='')
                console.print()
            else:
                def brlnum(n1,n2):
                    match n1:
                        case 0: d1 = 0x00
                        case 1: d1 = 0x01
                        case 2: d1 = 0x03
                        case 3: d1 = 0x07
                        case 4 | -4: d1 = 0x47
                        case -1: d1 = 0x40
                        case -2: d1 = 0x44
                        case -3: d1 = 0x46
                    match n2:
                        case 0: d2 = 0x00
                        case 1: d2 = 0x08
                        case 2: d2 = 0x18
                        case 3: d2 = 0x38
                        case 4 | -4: d2 = 0xB8
                        case -1: d2 = 0x80
                        case -2: d2 = 0xA0
                        case -3: d2 = 0xB0
                    return d1+d2
                for c in range(start,stop-1,step):
                    v=brlnum(self.gdf.loc[i][c],self.gdf.loc[i][c+1])
                    # clrincr = (pow(2,self.df['v'][c])-vlmin)*127//vlrange
                    if v!=0:
                        # color = f"rgb({128+clrincr},{int(self.df['v'][c]*5)},{100+clrincr//2})"
                        color = colorrgb(self.df['vp'][c])
                        row+=f'[{color}]{chr(0x2800+v)}[/{color}]'
                        # row+=f'{chr(0x2800+v)}'
                    else:
                        if c%60==44:
                            color = 'grey15'
                            # row+=f'[{color}]{chr(0x2800+v)}[/{color}]'
                            row+=f'[{color}]{chr(0x2847)}[/{color}]'
                        else:
                            row+=f'{chr(0x2800+v)}'
                    # if self.df['v'][c]>(self.df['v'].max()+self.df['v'].min())//2:
                    #     color+= ' blink'
                    # console.print(f'[{color}]{chr(0x2800+v)}[/{color}]', end='')
                yield row
        # console.print(f'{"":>7s}', end='')
        row=chr(0x2800)
        for c in range(start,stop-5,step):
            row+='⠉'
        row='[steel_blue]'+row+'[/steel_blue]'
        row+=f'{self.lowerline/20:8.2f}'
        yield row
        
        upsidemove = 100*(self.upperline-self.df['o'][0])/self.df['o'][0]
    
        lowsidemove = 100*(self.df['o'][0]-self.lowerline)/self.df['o'][0]
        yield f"Open {self.df['o'][0]/20:8.2f} UpMove {upsidemove:4.2f}, DownMove {lowsidemove:4.2f}"
        # console.print()
        # console.print(f'{self.lowerline/20:7.2f}')
        t2 = time.time()
        # console.print(f'Rendered in {t2-t1:.2f} seconds.')
    def draw(self,squeeze=True):
        for row in self.getline(squeeze):
            console.print(row)
    def draw2(self):
        for i in self.gdf.index:
            print(f'{"⢸":>7s}', end='')
            for c in range(self.gdf.columns.start,self.gdf.columns.stop//2,2):
                def brlnum(n1,n2):
                    match n1:
                        case 0: d1 = 0x00
                        case 1: d1 = 0x01
                        case 2: d1 = 0x03
                        case 3: d1 = 0x07
                        case 4 | -4: d1 = 0x47
                        case -1: d1 = 0x40
                        case -2: d1 = 0x44
                        case -3: d1 = 0x46
                    match n2:
                        case 0: d2 = 0x00
                        case 1: d2 = 0x08
                        case 2: d2 = 0x18
                        case 3: d2 = 0x38
                        case 4 | -4: d2 = 0xB8
                        case -1: d2 = 0x80
                        case -2: d2 = 0xA0
                        case -3: d2 = 0xB0
                    return d1+d2
                v=brlnum(self.gdf.loc[i][c],self.gdf.loc[i][c+1])
                print(f'{chr(0x2800+v)}', end='')
            print()

if __name__ == '__main__':
    df =pd.DataFrame([[36700,36611,36680,36600,14],
[36500,36200,36440,36103,15],
[36625,36585,36504,36467,14],
[36655,36468,36605,36420,15],
[36578,36544,36512,36481,14],
[36580,36527,36559,36494,13],
[36776,36580,36760,36540,15],
[36760,36760,36699,36680,14],
[36725,36699,36722,36679,13],
[36748,36725,36640,36640,13],
[36700,36700,36650,36611,13],
[36700,36680,36670,36638,12],
[36673,36673,36653,36619,12],
[36665,36640,36653,36625,13],
[36658,36620,36615,36600,13],
[36660,36641,36653,36610,13],
[36951,36653,36930,36627,15],
[37120,36930,37101,36860,16],
[37158,37111,37048,36980,15],
[37059,37016,36884,36833,14],
[37074,36904,36979,36874,14],
[36980,36960,36931,36864,13],
[36960,36931,36908,36844,14],
[36959,36908,36932,36900,13],
[37036,36932,36965,36931,14],
[36990,36947,36923,36902,13],
[36941,36923,36842,36835,13],
[36900,36849,36776,36744,14],
[36864,36775,36829,36744,13],
[36840,36840,36821,36754,12],
[36898,36821,36881,36821,13],
[36920,36900,36877,36862,13],
[36954,36877,36839,36822,13],
[36870,36840,36851,36820,12],
[36877,36855,36808,36771,12],
[36807,36798,36800,36760,12],
[36828,36800,36752,36740,13],
[36799,36774,36799,36749,11],
[36869,36783,36809,36780,13],
[36872,36829,36871,36809,11],
[36967,36871,36960,36837,14],
[37040,36960,37040,36920,14],
[37059,37032,37039,36992,14],
[37069,37039,36993,36966,13],
[37020,36993,36997,36964,12]],columns=['h','o','c','l','v'])
    # print(df)

    # cc = CandleChart(df,32)
    # df1=df.assign(m=lambda x: x.l-100,w=lambda x: np.log2(x.h)+x.v)
    # df1=df.assign(m=lambda x: x.l-100)
    df1 = df
    df1['m'] = df1['l'].rolling(window=5).mean()
    df1=df1.assign(m=lambda x: np.ceil(x.m))
    # df1['m'] = df1['m'].apply(lambda x: np.ceil(x.m))


    # change color according to volume*price more vol*p5 mean green less vol*p5 mean red, shade according to maximum minimum vol
    df1['v'].apply(lambda x: np.power(2,x)).sum()
    
    cc = CandleChart(df1)
    # df1['d'].rolling(window=5).mean()
    if cc.df is not None:
        cc.displayData()
        cc.draw()

