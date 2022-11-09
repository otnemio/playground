import multiprocessing as mp
import pandas as pd, numpy as np, h5py
import os,time
from datetime import timedelta
from common import Today
manager = mp.Manager()


def check_for_indicators(dfs):
    # sharp_drop_then_increasing
    pass
def analyser(today:Today):
    dfs = {}
    while True:
        print('-------------------------------------------')
        now =today.now()
        j = int((now-today.time(9,15))/timedelta(minutes=1))
        with h5py.File(os.path.join('/tmp', "tmpfs", "savedmarket.hdf5"),"r") as hf:
            for instrument in hf.keys():
                dfs[instrument] = hf.get(instrument)
                check_for_indicators(dfs)
                
        time.sleep(10)

if __name__ == '__main__':
    backtest = 0 #int(input('Backtest Day: '))
    today = Today(backtest)
    jobs = []
    with mp.Pool() as pool:
            jobs.append(pool.apply_async(analyser, [today]))
            while True:
                time.sleep(60*60*10)