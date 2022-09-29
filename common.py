from datetime import datetime,timedelta
import pandas as pd, numpy as np
import time, os, glob, random

class Today:
    def __init__(self, backtest) -> None:
        self.init = datetime.now()
        self.backtest = backtest
        self.bnow = self.time(9,10)
        if self.backtest>0:
            self.bt = Backtest(91)
            self.init = self.bnow


    def time(self,hour:int,min:int):
        return self.init.replace(hour=hour, minute=min, second=0, microsecond=0)
    def now(self):
        if self.backtest > 0:
            now = self.bnow
        else:
            now = datetime.now() #- timedelta(hours=10)
        return now
    def sleep(self, nsec:float):
        if self.backtest > 0:
            self.bnow += timedelta(seconds=nsec)
        else:
            time.sleep(nsec)
    def currentp5(self,instrument):
        today0915 = self.time(9,15)
        if self.bnow < today0915:
            timeblock = 1
            floatingtime = 0
        else:
            timeblock = int((self.bnow - today0915)/timedelta(minutes=5)+1)
            floatingtime = (self.bnow - today0915)/timedelta(minutes=5) %1
        
        return self.bt.p5(instrument,timeblock,floatingtime)


class Backtest:
    def __init__(self,btmktday) -> None:
        path = os.path.dirname(os.path.realpath(__file__))
        all_files = glob.glob(os.path.join(path,'data', "*.???.??.csv"))
        li = []
        for file_name in all_files:
            df = pd.read_csv(file_name, index_col=None, header=0)
            nicename = file_name.rpartition('/')[2].split('.')[0]
            exchange = file_name.rpartition('/')[2].split('.')[1]
            df2 = df.assign(Instrument = f'{nicename}.{exchange[0]}')
            li.append(df2)
        frame = pd.concat(li, axis=0, ignore_index=True)
        frame.set_index(['DoY','Instrument','M5'], inplace=True)
        # self.df = frame.loc['APOLLOTYRE','NSE',91]
        # self.frame.sort_index()
        # self.frame.sort_index(level='DoY')
        self.DoY = self.DoYfromBtD(btmktday)
        self.dframe = frame.loc[self.DoY]
        self.InstrumentListUpdate()
    
    def InstrumentListUpdate(self):
        self.instruLst = []
        for ins in self.dframe.index.get_level_values('Instrument').drop_duplicates():
            self.instruLst.append(ins)

    def p5(self,instrument:str,timeblock:int,floatingtime:float):
        hi = self.dframe.loc[instrument]['High'][timeblock]
        op = self.dframe.loc[instrument]['Open'][timeblock]
        cl = self.dframe.loc[instrument]['Close'][timeblock]
        lo = self.dframe.loc[instrument]['Low'][timeblock]
        if op > cl:
            if floatingtime < 0.25:
                price5p = op + (hi-op)*random.random()*floatingtime/0.25
            elif floatingtime < 0.75:
                price5p = hi - (hi-lo)*random.random()*(floatingtime-0.25)/0.5
            else:
                price5p = lo + (cl-lo)*random.random()*(floatingtime-0.75)/0.25
        else:
            if floatingtime < 0.25:
                price5p = op - (op-lo)*random.random()*floatingtime/0.25
            elif floatingtime < 0.75:
                price5p = lo + (hi-lo)*random.random()*(floatingtime-0.25)/0.5
            else:
                price5p = hi - (hi-cl)*random.random()*(floatingtime-0.75)/0.25
        return int(price5p)
    
    def DoYfromBtD(self,btmktday:int):
        return btmktday
        day = datetime.date(datetime.now()-timedelta(days=btmktday))
        if btmktday==0:
            return day.timetuple().tm_yday

    def display(self):
        # print(f'DoY {self.DoY} Summary')
        # print(self.dframe)
        print(self.p5('BEL','NSE'))

if __name__ == '__main__':
    today =Today(True)
    bt = Backtest(91)
    for instru in today.bt.instruLst:
        nicename = instru.split('.')[0]
        exchange = instru.split('.')[1]
        # p5 = instru[2]
        print(f'{nicename} {exchange}')

    # today.bt.display()