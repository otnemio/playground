import multiprocessing as mp
from rich.align import Align
from rich.live import Live
from rich.table import Table
from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel

import grpc, time, ctypes, sys, shutil
from pynput import keyboard
import pandas as pd, numpy as np, h5py, os
from candlechart import CandleChart
from datetime import datetime, timedelta
import logging
from rich.logging import RichHandler
import flykite_pb2
import flykite_pb2_grpc

display_console = Console(stderr=False)
input_console = Console(stderr=False)

manager = mp.Manager()

shared_dict = manager.dict()
shared_dict['graph']=manager.list()
shared_dict['instruments']=manager.list()
shared_dict_analysis = manager.dict()
shared_dict_sideboard = manager.dict()

mltp_msg = manager.Value(ctypes.c_char_p, "----------")
mltp_state = manager.Value(ctypes.c_char_p, "----------")

def make_layout() -> Layout:
    """Define the layout."""
    layout = Layout(name="root")
    
    layout.split(
        Layout(name="header",size=3),
        Layout(name="body",minimum_size=40),
        Layout(name="footer"),
    )
    layout["body"].split_row(Layout(name="side"), Layout(name="terminal",minimum_size=200))
    layout["side"].split_column(Layout(name="box1"), Layout(name="box2"))
    
    layout["header"].update(Header())
    layout["terminal"].update(BigScreen())
    layout["box1"].update(UpSideBoard())
    layout["box2"].update(LowSideBoard())
    return layout

class BigScreen:
    
    def __rich__(self) -> Panel:
        
        table = Table(box=None)
        # table.add_column("⣀")
        # table.add_column("⣀")
        # table.add_column("⣀")
        for row in shared_dict['graph']:
            table.add_row(row)
        
        return Panel(table, title=f"[green]{mltp_state.value}",border_style="yellow")
class UpSideBoard:
    def __rich__(self) -> Panel:
        grid = Table.grid(expand=True)
        grid.add_column(justify="left", ratio=1)
        grid.add_column(justify="right")
        for item in shared_dict['instruments']:
            grid.add_row(
                f"{item}",""
            )
        return Panel(grid, title=f"[medium_spring_green]Instruments", border_style="chartreuse4")    
class LowSideBoard:
    def __rich__(self) -> Panel:
        grid = Table.grid(expand=True)
        grid.add_column(justify="left", ratio=1)
        grid.add_column(justify="right")
        if 'data' in shared_dict_sideboard:
            for key,value in shared_dict_sideboard['data'].items():
                grid.add_row(
                    f"{key}", f"{value}"
                )
        return Panel(grid, title=f"[green]{mltp_state.value}", border_style="chartreuse4")    
class Header:
    """Display header with clock."""

    def __rich__(self) -> Panel:
        grid = Table.grid(expand=True)
        grid.add_column(justify="center", ratio=1)
        grid.add_column(justify="center", ratio=1)
        grid.add_column(justify="center", ratio=1)
        
        now = datetime.now()
        tup=('Ⓜ','Ⓣ','Ⓦ','Ⓣ','Ⓕ')
        week = "<-"
        for d in range(5):
            if d == now.weekday():
                week += f"[cyan]{tup[d]:2}[/cyan]"
            else:
                week += f"{tup[d]:2}"
        week += "->"
        grid.add_row(
            f'{mltp_msg.value}. Happy Earning.',
            week,
            now.strftime(f"%H:%M:%S %d %B %Y")
        )
        return Panel(grid, style="#CAD2D8 on #154360")

def Dashboard():
    live = Live(make_layout(),refresh_per_second=2, screen=True, console=display_console)
    live.start()

def fetchCandles(stub:flykite_pb2_grpc.KiterStub):
    instruments = stub.FetchInstruments(flykite_pb2.KiteRequest(msg='all'))
    for instrument in instruments:
        
        # logging.warning(instrument.nicename)
        candlesticks = stub.FetchCandles(flykite_pb2.Instrument(nicename = instrument.nicename, exchange = instrument.exchange))
        if candlesticks:
            arr = np.empty((0,5),int)
            dataPresent = False
            for candlestick in candlesticks:
                # logging.warning(candlestick.p5high)
                if candlestick.p5high>0:
                    dataPresent = True
                    arr = np.append(arr,np.array([[candlestick.p5high,candlestick.p5open,candlestick.p5close,candlestick.p5low,candlestick.volg]]),axis=0)
                else:
                    break
            if dataPresent:
                df = pd.DataFrame(arr,columns=['h','o','c','l','v'])
                cc = CandleChart(df,32)
                # shared_dict["graph"][:]=[]
                lst=[]
                for row in cc.getline():
                    lst.append(row)
                    
                # logging.warning(len(lst))
                i=0
                for r in lst:
                    # logging.warning(r)
                    if len(shared_dict["graph"])<32:
                        shared_dict["graph"].append(r)
                    else:
                        shared_dict["graph"][i]=r
                    i+=1
                mltp_state.set(instrument.nicename)
                time.sleep(1)
            # mltp_msg.set(shared_dict["graph"][12][0:5])
def fetchMemInstruments(): 
    with h5py.File(os.path.join('/tmp', "tmpfs", "savedmarket.hdf5"),"r") as hf:
        for instrument in hf.keys():
            shared_dict['instruments'].append(instrument)
def fetchMemCandles():
    dfs={}
    hrn = 32
    # pd.set_option("display.max_rows", None, "display.max_columns", None)
    # mltp_state.set('M&M.N')
    with h5py.File(os.path.join('/tmp', "tmpfs", "savedmarket.hdf5"),"r") as hf:
        # for instrument in hf.keys():
            instrument = mltp_state.value
            t0=time.time()
            logging.warning(instrument)
            dfs[instrument]=hf.get(instrument)
            df = pd.DataFrame(data=np.array(dfs[instrument]),columns=['h','o','c','l','v'])
            # if len(df.query('h>0'))==0 or df.query('h>0').tail(1).index+len(df.query('h<=0'))!=374:
            #     continue
            cc = CandleChart(df.query('h>0'),hrn)
            # shared_dict["graph"][:]=[]
            lst=[]
            for row in cc.getline():
                lst.append(row)
                logging.warning(row)
            
            logging.error(len(lst))
            
            i=0
            for r in lst:
                
                if len(shared_dict["graph"])<hrn+3:
                    shared_dict["graph"].append(r)
                else:
                    shared_dict["graph"][i]=r
                i+=1
            mltp_state.set(instrument)
            t1=time.time()
            # time.sleep(5-t1+t0)
def fetch():
    stub = flykite_pb2_grpc.KiterStub(grpc.insecure_channel('localhost:50051'))
    while True:
        # fetchCandles(stub)
        fetchMemInstruments()
        fetchMemCandles()
        time.sleep(5)

if __name__ == '__main__':
    logging.disable()
    # logging.shutdown()
    logging.StreamHandler(sys.stderr)
    
    jobs = []
    _width, _height = shutil.get_terminal_size()
    display_console.size = (_width, _height-1)
    with mp.Pool() as pool:
        jobs.append(pool.apply_async(Dashboard, []))
        jobs.append(pool.apply_async(fetch, []))
        # keyboard.add_hotkey('page up, page down', lambda: keyboard.write('foobar'))
        
        def on_press(key):
            try:
                if key.char=='a':
                    mltp_state.set('ADANIGREEN.N')
                elif key.char=='r':
                    mltp_state.set('RELIANCE.N')
                elif key.char=='m':
                    mltp_state.set('M&M.N')
                elif key.char=='b':
                    mltp_state.set('BEL.N')
                elif key.char=='i':
                    mltp_state.set('ITC.N')
                elif key.char=='h':
                    mltp_state.set('HINDUNILVR.N')
                elif key.char=='t':
                    mltp_state.set('TCS.N')
                
                # print('alphanumeric key {0} pressed'.format(
                #     key.char))

            except AttributeError:
                # print('special key {0} pressed'.format(
                #     key))
                pass

        def on_release(key):
            fetchMemCandles()
            # print('{0} released'.format(
            #     key))
            if key == keyboard.Key.esc:
                # Stop listener
                return False

        # Collect events until released
        with keyboard.Listener(
                on_press=on_press,
                on_release=on_release) as listener:
            listener.join()

        # ...or, in a non-blocking fashion:
        listener = keyboard.Listener(
            on_press=on_press,
            on_release=on_release)
        listener.start()