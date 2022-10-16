from concurrent import futures
import multiprocessing as mp
# from technicalanalysis import TechnicalAnalysis
from pathlib import Path
from kite import Kite
from mconfig import readConfig
from common import Today
# from rdsins import RdsIns
import os, sys, time, math, logging, shutil, csv, glob
from rich.logging import RichHandler
import pandas as pd, numpy as np, h5py
from datetime import datetime, timedelta
import grpc
import flykite_pb2
import flykite_pb2_grpc
from google.protobuf.timestamp_pb2 import Timestamp

manager = mp.Manager()
lock = mp.Lock()
shared_dict = manager.dict()

def initialize():
    FORMAT = "%(message)s"
    logging.basicConfig(
        level="INFO", format=FORMAT, datefmt="[%X]", handlers=[RichHandler(markup=True)]
    )
    
    # logging.basicConfig(format='%(asctime)s %(message)s', datefmt='%d %b %Y %I:%M:%S %p')
    # logging.getLogger().setLevel(logging.DEBUG)

    shared_dict['orders']={'Sell-Buy':manager.list(),'Buy-Sell':manager.list(),'Kite-Exec':manager.list(),'Kite-Open':manager.list()}
    shared_dict['instruments']=manager.dict()
    shared_dict['Flag_KOU']=False
    shared_dict['Flag_AUTO']=False
    shared_dict['Flag_EXIT']=False
    shared_dict['Flag_FEXIT']=False
    shared_dict['Flag_MIDWORK']=False

class Kiter(flykite_pb2_grpc.KiterServicer):
    # def ReturnVal(self, request, context):
    #     return flykite_pb2.Instrument(name=request.name ,exchange='N',p5=2200)
    def __init__(self, today) -> None:
        super().__init__()
        self.today = today
        # self.ri = RdsIns(clear=True if today.now() < today.time(9,10) else False)
    
    def Command(self, request, context):
        flag = f'Flag_{request.msg.upper()}'
        shared_dict[flag] = not shared_dict[flag]
        return flykite_pb2.KiteReply(msg=f"'{flag}' updated. Current value is {shared_dict[flag]}")
    
    def FetchCandles(self, request, context):
        instrument = f'{request.nicename}.{flykite_pb2.Instrument.Exchange.Name(request.exchange)[0]}'
        dataPresent = False
        for i in range(0,375):
            if instrument not in shared_dict['instruments'].keys():
                break
            ch = shared_dict['instruments'][instrument]['h'][i]
            co = shared_dict['instruments'][instrument]['o'][i]
            cc = shared_dict['instruments'][instrument]['c'][i]
            cl = shared_dict['instruments'][instrument]['l'][i]
            vg = shared_dict['instruments'][instrument]['v'][i]
            if co > 0:
                dataPresent = True
                # ta = TechnicalAnalysis(shared_dict['instruments'])
                yield flykite_pb2.CandleStick(minuteindex = i, p5high = ch, p5open = co, p5close = cc, p5low = cl, volg = vg)
            elif dataPresent == True:
                # logging.info(ta.SMA(instrument,5).loc[i-5:i-1]/20)
                break
        if dataPresent is False:
            yield flykite_pb2.CandleStick(minuteindex = -1, p5high = -1, p5open = -1, p5close = -1, p5low = -1, volg = -1)

    def FetchInstruments(self, request, context):
        if request.msg.lower()=='all':
            for instrument in shared_dict['instruments'].keys():
                nicename=instrument.split('.')[0]
                exchange = flykite_pb2.Instrument.Exchange.NSE if instrument.split('.')[1] == 'N' else flykite_pb2.Instrument.Exchange.BSE
                yield flykite_pb2.Instrument(nicename=nicename,exchange=exchange)

    def ShowDict(self, request, context):
        # return flykite_pb2.KiteReply(msg=str(shared_dict['instruments']))
        for instrument in shared_dict['instruments'].keys():
            print(instrument)
        return flykite_pb2.KiteReply(msg=str(shared_dict['instruments']))
    
    def SubmitIfThenElseOrder(self, request, context):
        timestamporder = Timestamp()
        timestamporder.FromDatetime(self.today.now())
        timestampite = Timestamp()
        timestampite.FromDatetime(self.today.time(0,0))
        
        req_dict = lambda: {'nicename':request.instrument.nicename,
                        'exchange':request.instrument.exchange,
                        'quantity':request.quantity,
                        'p5if':request.p5if,
                        'p5then':request.p5then,
                        'p5else':request.p5else,
                        'statusif':flykite_pb2.OrderStatus.NOTSUBMITTED,
                        'statusthen':flykite_pb2.OrderStatus.NOTSUBMITTED,
                        'statuselse':flykite_pb2.OrderStatus.NOTSUBMITTED,
                        'timeif': timestampite,
                        'timethen': timestampite,
                        'timeelse': timestampite,
                        'stoploss':request.stoploss,
                        'split': request.split,
                        'papertrade': request.papertrade,
                        'ordertime':timestamporder,
                        'orderby':'IC'
                    }
        if request.quantity < 1:
            return flykite_pb2.KiteReply(msg=f"Order submission [red]unsuccessful[/red]. Quantity should not be less than one.")
        elif request.quantity >= 1:
            if request.p5if>request.p5then and request.p5if<request.p5else:
                shared_dict['orders']['Sell-Buy'].append(req_dict())
                return flykite_pb2.KiteReply(msg=f"Order submission [green]successful[/green]. {request.quantity} Sell then Buy order(s).")
            elif request.p5if<request.p5then and request.p5if>request.p5else:
                shared_dict['orders']['Buy-Sell'].append(req_dict())
                return flykite_pb2.KiteReply(msg=f"Order submission [green]successful[/green]. {request.quantity} Buy then Sell order(s).")
        else:
            return flykite_pb2.KiteReply(msg=f"Order submission [red]unsuccessful[/red].")
        
    
    def FetchIfThenElseOrders(self, request, context):

        if request.msg.lower() == 'sb' or request.msg.lower() == 'all':
            for it in shared_dict['orders']['Sell-Buy']:
                yield flykite_pb2.OrderIfThenElse(instrument = flykite_pb2.Instrument(nicename = it['nicename'],
                                                                                  exchange = it['exchange']),
                                              quantity = it['quantity'],
                                              p5if = it['p5if'],
                                              p5then = it['p5then'],
                                              p5else = it['p5else'],
                                              statusif = it['statusif'],
                                              statusthen = it['statusthen'],
                                              statuselse = it['statuselse'],
                                              timeif = it['timeif'],
                                              timethen = it['timethen'],
                                              timeelse = it['timeelse'],
                                              stoploss = it['stoploss'],
                                              split = it['split'],
                                              papertrade = it['papertrade'],
                                              ordertime = it['ordertime'],
                                              orderby = it['orderby'])
        if request.msg.lower() == 'bs' or request.msg.lower() == 'all':
            for it in shared_dict['orders']['Buy-Sell']:
                yield flykite_pb2.OrderIfThenElse(instrument = flykite_pb2.Instrument(nicename = it['nicename'],
                                                                                  exchange = it['exchange']),
                                              quantity = it['quantity'],
                                              p5if = it['p5if'],
                                              p5then = it['p5then'],
                                              p5else = it['p5else'],
                                              statusif = it['statusif'],
                                              statusthen = it['statusthen'],
                                              statuselse = it['statuselse'],
                                              timeif = it['timeif'],
                                              timethen = it['timethen'],
                                              timeelse = it['timeelse'],
                                              stoploss = it['stoploss'],
                                              split = it['split'],
                                              papertrade = it['papertrade'],
                                              ordertime = it['ordertime'],
                                              orderby = it['orderby'])
    
    def ClearIfThenElseOrders(self, request, context):
        c = 0
        if request.msg.lower() == 'sb' or request.msg.lower() == 'all':
            for i,it in enumerate(shared_dict['orders']['Sell-Buy']):
                if it['statusif'] == flykite_pb2.OrderStatus.NOTSUBMITTED:
                    shared_dict['orders']['Sell-Buy'].pop(i)
                    c+=1
        if request.msg.lower() == 'bs' or request.msg.lower() == 'all':
            for i,it in enumerate(shared_dict['orders']['Buy-Sell']):
                if it['statusif'] == flykite_pb2.OrderStatus.NOTSUBMITTED:
                    shared_dict['orders']['Buy-Sell'].pop(i)
                    c+=1
        if c>0:
            return flykite_pb2.KiteReply(msg=f"Clearing of {c} order(s) [green]successful[/green].")
        else:
            return flykite_pb2.KiteReply(msg=f"No order(s) need to be cleared.")
    
    def FetchKiteOrders(self, request, context):
        def enm(status):
            if status == 'COMPLETE':
                return flykite_pb2.OrderStatus.COMPLETE
            if status == 'CANCELLED':
                return flykite_pb2.OrderStatus.CANCELLED
            if status == 'OPEN':
                return flykite_pb2.OrderStatus.OPEN
            
        if request.msg.lower() == 'open' or request.msg.lower() == 'all':
            for ki in shared_dict['orders']['Kite-Open']:
                yield flykite_pb2.OrderKite(instrument = flykite_pb2.Instrument(nicename = ki[2],
                                                exchange = flykite_pb2.Instrument.Exchange.NSE if ki[3] == 'NSE' else flykite_pb2.Instrument.Exchange.BSE),
                                            ordertime = Timestamp().FromDatetime(datetime.strptime(ki[0],'%H:%M:%S')),
                                            status = enm(ki[7]),
                                            trade = flykite_pb2.OrderKite.Trade.BUY if ki[1] == 'BUY' else flykite_pb2.OrderKite.Trade.SELL,
                                            product = flykite_pb2.OrderKite.Product.MIS if ki[4] == 'MIS' else flykite_pb2.OrderKite.Product.CNC,
                                            quantity = int(ki[5].split('/')[0]),
                                            avgp5 = int(float(ki[6].replace(',',''))*20)
                                            )

        if request.msg.lower() == 'cmpl' or request.msg.lower() == 'all':
            for ki in shared_dict['orders']['Kite-Exec']:
                if ki[7] == 'COMPLETE':
                    yield flykite_pb2.OrderKite(instrument = flykite_pb2.Instrument(nicename = ki[2],
                                                    exchange = flykite_pb2.Instrument.Exchange.NSE if ki[3] == 'NSE' else flykite_pb2.Instrument.Exchange.BSE),
                                                ordertime = Timestamp().FromDatetime(datetime.strptime(ki[0],'%H:%M:%S')),
                                                status = enm(ki[7]),
                                                trade = flykite_pb2.OrderKite.Trade.BUY if ki[1] == 'BUY' else flykite_pb2.OrderKite.Trade.SELL,
                                                product = flykite_pb2.OrderKite.Product.MIS if ki[4] == 'MIS' else flykite_pb2.OrderKite.Product.CNC,
                                                quantity = int(ki[5].split('/')[0]),
                                                avgp5 = int(float(ki[6].replace(',',''))*20)
                                                )
        if request.msg.lower() == 'cncl' or request.msg.lower() == 'all':
            for ki in shared_dict['orders']['Kite-Exec']:
                if ki[7] == 'CANCELLED':
                    yield flykite_pb2.OrderKite(instrument = flykite_pb2.Instrument(nicename = ki[2],
                                                    exchange = flykite_pb2.Instrument.Exchange.NSE if ki[3] == 'NSE' else flykite_pb2.Instrument.Exchange.BSE),
                                                ordertime = Timestamp().FromDatetime(datetime.strptime(ki[0],'%H:%M:%S')),
                                                status = enm(ki[7]),
                                                trade = flykite_pb2.OrderKite.Trade.BUY if ki[1] == 'BUY' else flykite_pb2.OrderKite.Trade.SELL,
                                                product = flykite_pb2.OrderKite.Product.MIS if ki[4] == 'MIS' else flykite_pb2.OrderKite.Product.CNC,
                                                quantity = int(ki[5].split('/')[0]),
                                                avgp5 = int(float(ki[6].replace(',',''))*20)
                                                )
        
        #     for ki in shared_dict['orders']['Kite-Open']:
        #         yield flykite_pb2.OrderIfThenElse(instrument = flykite_pb2.Instrument(nicename = ki['nicename'],
        #                                                                           exchange = ki['exchange']),
        #                                       quantity = ki['quantity'],
        #                                       p5if = ki['p5if'])
def serve(today:Today):
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    flykite_pb2_grpc.add_KiterServicer_to_server(Kiter(today), server)
    logging.info(f'{today.now():%H:%M:%S} Server [green blink]Started[/green blink]. Listening at [::]:50051')
    server.add_insecure_port('[::]:50051')
    server.start()
    server.wait_for_termination()


def kitelogin(headless,today:Today, PIN):
    if today.backtest == 0:
        kLogins=readConfig('kites')
        if kLogins:
            kite = Kite(headless,today, kLogins[0]['zId'], kLogins[0]['zPass'], PIN)
            logging.info(f"{today.now():%H:%M:%S} {kite.welcome_msg}")
    else:
        kite = Kite(headless,today)
        logging.info(f"{today.now():%H:%M:%S} Backtest Ready")
    return kite

def updateKiteOrders(kite:Kite):
    if shared_dict['Flag_KOU']:
        shared_dict['orders']['Kite-Open'][:]=[]
        shared_dict['orders']['Kite-Exec'][:]=[]
        for item in kite.orders('open'):
            shared_dict['orders']['Kite-Open'].append(item)
        for item in kite.orders('completed'):
            shared_dict['orders']['Kite-Exec'].append(item)
        shared_dict['Flag_KOU']=False


def flySecondKite(today:Today, headless):
    try:
        kLogins=readConfig('kites')
        if kLogins:
            kite2 = Kite(headless,today, kLogins[1]['zId'], kLogins[1]['zPass'], kLogins[1]['zPin'])
        logging.info(f"{today.now():%H:%M:%S} {kite2.welcome_msg}")
        dfs={}
        ti='1m'
        while True:
            for i in [7,1,7,2,7,1,7,2,7,1,7,3,7,1,7,2,7,1,7,3,7,1,7,4,7,1,7,2,7,1,7,3,7,1,7,4,7,1,7,5]:
                # give it some time
                today.sleep(0.5)
                insLst = []
                for insp in kite2.instruments(i):
                    insLst.append(insp[0])
                for instrument in insLst:
                    shared_dict['Flag_MIDWORK']=True
                    with h5py.File(os.path.join('/tmp', "tmpfs", "market.hdf5"),"a") as hf:
                        if instrument not in hf.keys():
                            hf.create_dataset(instrument,data=pd.DataFrame(np.full((375,5),0,dtype=int),columns=['h','o','c','l','v']))
                        dfs[instrument]=hf.get(instrument)
                        if dfs[instrument][373].all()>0:
                            logging.info(f'{instrument} data is complete.')
                            continue
                        kite2.timetoReturnChart=False
                        for item in kite2.fetchchartdata(instrument,ti):
                            if dfs[instrument][item[0]].any()<=0:
                                dfs[instrument][item[0]]=[item[1],item[2],item[3],item[4],item[5]]
                            else:
                                if ti=='1D' and dfs[instrument][3].all()>0:
                                        kite2.timetoReturnChart=True
                                elif ti=='1m':
                                    df = pd.DataFrame(data=np.array(dfs[instrument]),columns=['h','o','c','l','v'])
                                    if df.query('h>0').tail(1).index+len(df.query('h<=0'))==374:
                                        kite2.timetoReturnChart=True
                        shared_dict['instruments'][instrument]=pd.DataFrame(dfs[instrument],columns=['h','o','c','l','v'])
                        logging.info(f'{instrument} saved.')
                    shutil.copyfile(os.path.join('/tmp', "tmpfs", "market.hdf5"),os.path.join('/tmp', "tmpfs", "savedmarket.hdf5"))
                    logging.info(f'backup created.')
                    shared_dict['Flag_MIDWORK']=False
                    if shared_dict['Flag_EXIT']:
                        shared_dict['Flag_FEXIT']=True
                        logging.info('EXIT signal received by second kite, returning...')
                        return
                    today.sleep(2)
                kite2.driver.switch_to.window(kite2.original_window)
            today.sleep(5)
    except:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        logging.error(f'{exc_type}, {fname}, {exc_tb.tb_lineno}')
        return False
    
def readCSV():
    # path = os.path.dirname(os.path.realpath(__file__))
    all_files = glob.glob(os.path.join(Path.home(),'Downloads', "chart*.csv"))
    li = []
    dfs = {}
    p5 = lambda s: int(float(s)*20)
    for file_name in all_files:
        df = pd.read_csv(file_name, index_col=None, header=0)
        os.remove(file_name)
        instrument = f"{df.columns[1].rpartition(' ')[2]}.N"
        df1 = df.assign(mi = pd.to_datetime(df['DateTime']).apply(lambda x: (x.hour-9)*60+x.minute-15)).groupby('mi').agg({df.columns[2]:['max','first','last','min']}).loc[0:374]
        shared_dict['Flag_MIDWORK']=True
        with h5py.File(os.path.join('/tmp', "tmpfs", "market.hdf5"),"a") as hf:
            if instrument not in hf.keys():
                hf.create_dataset(instrument,data=pd.DataFrame(np.full((375,5),0,dtype=int),columns=['h','o','c','l','v']))
            dfs[instrument]=hf.get(instrument)
            # dfs[instrument][item[0]]=[item[1],item[2],item[3],item[4],item[5]]
            for i, row in df1.iterrows():
                dfs[instrument][i]=[p5(row[0]),p5(row[1]),p5(row[2]),p5(row[3]),0]
            shared_dict['instruments'][instrument]=pd.DataFrame(dfs[instrument],columns=['h','o','c','l','v'])
            logging.info(f'{instrument} saved. len {len(df1)}')
        shutil.copyfile(os.path.join('/tmp', "tmpfs", "market.hdf5"),os.path.join('/tmp', "tmpfs", "savedmarket.hdf5"))
        logging.info(f'backup created.')
        shared_dict['Flag_MIDWORK']=False

def flyKite(today:Today, headless, PIN):
    kite = kitelogin(headless,today, PIN)
    prep = False
    safe = False
    dfs = {}
    n = 2
    while not shared_dict['Flag_EXIT']:
        # do not overload portal
        # start_time=time.time()
        today.sleep(n)
        readCSV()
        try:
            
            withinMarketTime = lambda t : t >= today.time(9,15) and t < today.time(15,20)
            now = today.now()
            if withinMarketTime(now) and today.backtest == 0:
                for i in range(1,2):
                    # give it some time
                    today.sleep(0.5)
                    # mid2_time=time.time()
                    # mid3_time=time.time()
                    for item in kite.instruments(i):
                        instrument=item[0]
                        p5=item[1]
                        with h5py.File(os.path.join('/tmp', "tmpfs", "market.hdf5"),"a") as hf:
                            if instrument not in hf.keys():
                                hf.create_dataset(instrument,data=pd.DataFrame(np.full((375,5),0,dtype=int),columns=['h','o','c','l','v']))
                            dfs[instrument]=hf.get(instrument)
                            update(dfs, today, now, instrument, p5)
                            shared_dict['instruments'][instrument]=pd.DataFrame(dfs[instrument],columns=['h','o','c','l','v'])
                            logging.info(f'{instrument} saved.')
                        shutil.copyfile(os.path.join('/tmp', "tmpfs", "market.hdf5"),os.path.join('/tmp', "tmpfs", "savedmarket.hdf5"))
                        logging.info(f'backup created.')

                        if shared_dict['Flag_AUTO']:
                            analyse_and_submit(dfs,today,now, instrument, p5)
                        if not safe:
                            safe = isSafe()
                        processOrders(instrument, p5, kite)
                
            elif withinMarketTime(now) and today.backtest > 0:
                # mid3_time=time.time()
                
                for item in kite.instruments():
                    update(dfs, today, now, instrument=item[0], p5=item[1])
                    if shared_dict['Flag_AUTO']:
                        analyse_and_submit(dfs,today,now, instrument=item[0], p5=item[1])
                    if not safe:
                        safe = isSafe()
                    processOrders(instrument=item[0], p5=item[1], kite=kite)
                
                # mid4_time=time.time()
                # logging.info(f'{today.now():%H:%M:%S} market is open')
            elif now<today.time(9,10) and now.second%60<n:
                logging.info(f'{now:%H:%M:%S} market is yet to open.')
            elif now<today.time(9,15) and now.second%60<n:
                if not prep:
                    #wip: only one time even if server restarts
                    # prepare(today,now,kite)
                    prep = True
                logging.info(f'{now:%H:%M:%S} market is settled.')
            elif now>=today.time(15,30):
                logging.info(f'{now:%H:%M:%S} market has closed.')
                shared_dict['Flag_EXIT'] = True
            # end_time=time.time()
            # logging.info(f'{today.now():%H:%M:%S} {shared_dict["Flag_EXIT"]} {mid1_time-start_time:10.7f} {mid2_time-start_time:10.7f} {mid3_time-start_time:10.7f} {mid4_time-start_time:10.7f} {end_time-start_time:10.7f}')
        except:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            logging.error(f'{exc_type}, {fname}, {exc_tb.tb_lineno}')
    if shared_dict['Flag_EXIT']:
        shared_dict['Flag_FEXIT']=True
        logging.info('EXIT signal received by first kite, returning...')
        return


def prepare(today:Today,now,kite:Kite):
    for item in kite.dict['hdl'].items():
        instrument = item[0]
        squant = math.ceil(item[1][0]*0.8)
        sp5 = int(item[1][2]*20*0.99)
        bp5 = int(item[1][2]*20*0.8)
        np5 = int(item[1][2]*20*1.2)
        submitOrder(today,now,instrument,quantity=squant,p5if=sp5,p5then=bp5,p5else=np5,stoploss=False,split=False,orderby='SF')


        
def update(dfs,today:Today, now:datetime, instrument:str, p5:int):
    j = int((now-today.time(9,15))/timedelta(minutes=1))
    h=dfs[instrument][j][0]
    o=dfs[instrument][j][1]
    c=dfs[instrument][j][2]
    l=dfs[instrument][j][3]
    v=dfs[instrument][j][4]
    if o>=0:
        c=p5
        if h<p5:
            h=p5
        if l>p5:
            l=p5
    else:
        h=p5
        o=p5
        c=p5
        l=p5
    dfs[instrument][j]=[h,o,c,l,v]


def analyse_and_submit(dfs, today:Today,now:datetime,instrument:str, p5:int):
    iswithin = lambda t1, t2: now>today.time(t1[0],t1[1]) and now<=today.time(t2[0],t2[1])
    enter_exit_minp5 = lambda point=1: math.ceil(p5*0.001*point)
    j = int((now-today.time(9,15))/timedelta(minutes=1))
    def sellifup():
        
        if ( p5 ==  dfs[instrument]['h'][j] and
        dfs[instrument]['h'][j] > dfs[instrument]['h'][j-1] and
        dfs[instrument]['h'][j-1] > dfs[instrument]['h'][j-2] and
        dfs[instrument]['h'][j-2] > dfs[instrument]['h'][j-3] and
        dfs[instrument]['h'][j-3] > dfs[instrument]['h'][j-4] ):
            # print(f' same high and low for current and previous minute for {instrument} {h} {l}')
            submitOrder(today,now,instrument,1,p5,p5-enter_exit_minp5(),p5+enter_exit_minp5(10))
    if iswithin((9,20),(9,30)):
        pass
    if iswithin((9,30),(10,15)):
        pass
    if iswithin((9,30),(12,0)):
        sellifup()
    


def submitOrder(today:Today,now:datetime,instrument:str,quantity:int,p5if:int,p5then:int,p5else:int,stoploss:bool=True,split:int=1,papertrade:bool=True,orderby:str='AL'):
    nicename = instrument.split('.')[0]
    exchange = f'{instrument.split(".")[1]}SE'
    timestamporder = Timestamp()
    timestamporder.FromDatetime(today.now())
    timestampite = Timestamp()
    timestampite.FromDatetime(today.time(0,0))
    req_dict = lambda: {'nicename':nicename,
                    'exchange':flykite_pb2.Instrument.Exchange.NSE if exchange == 'NSE' else flykite_pb2.Instrument.Exchange.BSE,
                    'quantity':quantity,
                    'p5if':p5if,
                    'p5then':p5then,
                    'p5else':p5else,
                    'statusif':flykite_pb2.OrderStatus.NOTSUBMITTED,
                    'statusthen':flykite_pb2.OrderStatus.NOTSUBMITTED,
                    'statuselse':flykite_pb2.OrderStatus.NOTSUBMITTED,
                    'timeif': timestampite,
                    'timethen': timestampite,
                    'timeelse': timestampite,
                    'stoploss': stoploss,
                    'split' : split,
                    'papertrade': papertrade,
                    'ordertime': timestamporder,
                    'orderby': orderby
        }
    if quantity < 1:
        msg=f"Order submission [red]unsuccessful[/red]. Quantity should not be less than one."
    elif quantity >= 1:
        if p5if>p5then and p5if<p5else:
            shared_dict['orders']['Sell-Buy'].append(req_dict())
            msg=f"Order submission [green]successful[/green]. {quantity} Sell then Buy order(s)."
        elif p5if<p5then and p5if>p5else:
            shared_dict['orders']['Buy-Sell'].append(req_dict())
            msg=f"Order submission [green]successful[/green]. {quantity} Buy then Sell order(s)."
    else:
        msg=f"Order submission [red]unsuccessful[/red]."
    # logging.info(f'{today.now():%H:%M:%S} {msg} {req_dict()}')
    return msg

def isSafe():
    safe = True
    for it in shared_dict['orders']['Sell-Buy']:
        if it['orderby'] == 'SF':
            if not it['statusif']==flykite_pb2.OrderStatus.COMPLETE:
                safe = False
                logging.info(f"{it['nicename']} not safe.")
    if safe:
        logging.info(f"All instruments are safe.")
    return safe
    
def processOrders(instrument:str,p5:int,kite:Kite):
    nicename = instrument.split('.')[0]
    exchange = f'{instrument.split(".")[1]}SE'
    def process(_enter,_exit):
        try:
            enter_exit=f'{_enter}-{_exit}'
            for i,it in enumerate(shared_dict['orders'][enter_exit]):
                if nicename == it['nicename'] and exchange == flykite_pb2.Instrument.Exchange.Name(it['exchange']) and not(it['statusthen']==flykite_pb2.OrderStatus.COMPLETE or it['statuselse']==flykite_pb2.OrderStatus.COMPLETE):
                    process_index = i
                    modified = False
                    splited = False
                    it = shared_dict['orders'][enter_exit][process_index]
                    jt = shared_dict['orders'][enter_exit][process_index]
                    timestampnow = Timestamp()
                    
                    enter_exit_minp5 = lambda point=1: math.ceil(p5*0.001*point)
                    enter_loss_p5 =  lambda point=1: math.ceil(abs(it['p5if']-it['p5else'])*point)
                    #entry must be confirmed on the spot
                    enter_trigger_is_hit = lambda cur_val: cur_val <= it['p5if']+enter_exit_minp5(0.8) and cur_val >= it['p5if'] if enter_exit == 'Sell-Buy' else cur_val >= it['p5if']-enter_exit_minp5(0.8) and cur_val <= it['p5if']
                    #exit can be confirmed later
                    def exit_trigger_is_hit(cur_val):
                        timenow = Timestamp()
                        timenow.FromDatetime(kite.today.now())
                        tlen = timenow.seconds - it['timeif'].seconds
                        if enter_exit == 'Sell-Buy':
                            # return cur_val <= (it['p5then']-enter_exit_minp5(2*math.sin(tlen*math.pi/300) if tlen<=300 else 0))
                            return cur_val <= it['p5then']-enter_exit_minp5()
                        else:
                            # return cur_val >= (it['p5then']+enter_exit_minp5(2*math.sin(tlen*math.pi/300) if tlen<=300 else 0))
                            return cur_val >= it['p5then']+enter_exit_minp5()
                    stoploss_trigger_is_hit = lambda cur_val: cur_val >= it['p5else'] if enter_exit == 'Sell-Buy' else cur_val <= it['p5else']
                    pos_not_taken = lambda: it['statusif']==flykite_pb2.OrderStatus.NOTSUBMITTED
                    entered = lambda: it['statusif']==flykite_pb2.OrderStatus.COMPLETE
                    not_exited = lambda: it['statusthen']!=flykite_pb2.OrderStatus.COMPLETE and it['statuselse']!=flykite_pb2.OrderStatus.COMPLETE
                    
                    def split(fixedloss=True):
                        if it['split']>1:
                            spread=1/it['split']
                            jt['p5if'] = it['p5if']+enter_loss_p5(spread) if enter_exit == 'Sell-Buy' else it['p5if']-enter_loss_p5(spread)
                            jt['p5then'] = it['p5then']+enter_loss_p5(spread) if enter_exit == 'Sell-Buy' else it['p5then']-enter_loss_p5(spread)
                            if fixedloss:
                                jt['p5else'] = it['p5else']
                            else:    
                                jt['p5else'] = it['p5else']+enter_exit_minp5() if enter_exit == 'Sell-Buy' else it['p5else']-enter_exit_minp5()
                            jt['split'] = it['split']-1
                            it['split'] = 1
                            return True
                        return False

                    def shift_and_rectify(cur_val):
                        # wip
                        shift_ratio = cur_val/it['p5if']
                        it['p5if'] = int(it['p5if'] * shift_ratio)
                        it['p5then'] = int(it['p5then'] * shift_ratio)
                        it['p5else'] = int(it['p5else'] * shift_ratio)
                        multiplier = 1 if it['stoploss'] else 10
                        it['p5then'] = min(it['p5then'],it['p5if'] - enter_exit_minp5()) if enter_exit == 'Sell-Buy' else max(it['p5then'],it['p5if'] + enter_exit_minp5())
                        it['p5else'] = max(it['p5else'],it['p5if'] + multiplier*enter_exit_minp5()) if enter_exit == 'Sell-Buy' else min(it['p5else'],it['p5if'] - multiplier*enter_exit_minp5())
                        return True
                        
                    def take_pos():
                        exectime = kite.trade(nicename=nicename,exchange=exchange,quantity=it['quantity'],tradetype=_enter,atprice='Limit',p5=it['p5if'],papertrade=it['papertrade'])
                        if exectime is not None:
                            it['statusif'] = flykite_pb2.OrderStatus.COMPLETE
                            timestampnow.FromDatetime(exectime)
                            it['timeif'] = timestampnow
                            return True
                        return False

                        
                    def exit_pos(cur_val):
                        if enter_exit == 'Sell-Buy':
                            it['p5then'] = cur_val+enter_exit_minp5(0.2)
                        else:
                            it['p5then'] = cur_val-enter_exit_minp5(0.2)
                        exectime = kite.trade(nicename=nicename,exchange=exchange,quantity=it['quantity'],tradetype=_exit,atprice='Limit',p5=it['p5then'],papertrade=it['papertrade'])
                        if exectime is not None:
                            it['statusthen'] = flykite_pb2.OrderStatus.COMPLETE
                            timestampnow.FromDatetime(exectime)
                            it['timethen'] = timestampnow
                            return True
                        return False
                        
                    def stop_loss():
                        exectime = kite.trade(nicename=nicename,exchange=exchange,quantity=it['quantity'],tradetype=_exit if it['stoploss'] else _enter,atprice='Market',p5=it['p5else'],papertrade=it['papertrade'])
                        if exectime is not None:
                            it['statuselse'] = flykite_pb2.OrderStatus.COMPLETE
                            timestampnow.FromDatetime(exectime)
                            it['timeelse'] = timestampnow
                            return True
                        return False
                        
                    if pos_not_taken():
                        if enter_trigger_is_hit(p5):
                            # stop shifting and rectification for now
                            # modified = shift_and_rectify(p5)
                            splited = split()
                            modified = take_pos()
                    if entered():
                        if exit_trigger_is_hit(p5):
                            modified = exit_pos(p5)
                        if not_exited() and stoploss_trigger_is_hit(p5):
                            modified = stop_loss()
                    
                    if modified:
                        shared_dict['orders'][enter_exit].pop(process_index)
                        shared_dict['orders'][enter_exit].append(it)
                        if splited:
                            shared_dict['orders'][enter_exit].append(jt)
        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            logging.error(f'{exc_type}, {fname}, {exc_tb.tb_lineno}')
    process(_enter='Sell',_exit='Buy')
    process(_enter='Buy',_exit='Sell')

def scrapefromNSE():
    pass

def analyser(today:Today):
    while True:
        time.sleep(10)
        print('-------------------------------------------')
        for instrument in shared_dict['instruments'].keys():
            print(instrument)
            hocl = shared_dict['instruments'][instrument]
            for i in range(0,375):
                if hocl['o'][i] > -1:
                    print(f"{instrument} {i} {hocl['h'][i]} {hocl['o'][i]} {hocl['c'][i]} {hocl['l'][i]}")

if __name__ == '__main__':
    initialize()
    headless = True #if input('Headless: ').lower()[0] == 'y' else False
    backtest = 0 #int(input('Backtest Day: '))
    if backtest:
        headless = True
    logging.info(f'headless: {headless}, backtest: T - {backtest}')
    today = Today(backtest)
    jobs = []
    PIN = input("Mobile App Code ")
    with mp.Pool() as pool:
        jobs.append(pool.apply_async(flyKite, [today, headless, PIN]))
        # jobs.append(pool.apply_async(flySecondKite, [today, headless]))
        # jobs.append(pool.apply_async(scrapefromNSE, []))
        jobs.append(pool.apply_async(serve, [today]))
        # jobs.append(pool.apply_async(analyser, [today]))
        
        while True:
            time.sleep(15)
            if shared_dict['Flag_FEXIT'] and not shared_dict['Flag_MIDWORK']:
                logging.info(f'{today.now():%H:%M:%S} Server [red blink]Stopped[red blink].')
                exit()
