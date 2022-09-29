from multiprocessing import Pool
from rich.prompt import Prompt
from rich.align import Align
from rich.live import Live
from rich.table import Table
from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich import box
from candlechart import CandleChart
import grpc, math, pandas as pd, numpy as np
from datetime import datetime, timedelta
import flykite_pb2
import flykite_pb2_grpc

# to make prompt work as expected and for history feature
import readline

input_console = Console(stderr=False)

def command(stub:flykite_pb2_grpc.KiterStub,msg):
    req = flykite_pb2.KiteRequest(msg=msg)
    res = stub.Command(req)
    input_console.print(res.msg)
    
def fetchKiteOrders(stub:flykite_pb2_grpc.KiterStub,msg):
    req = flykite_pb2.KiteRequest(msg=msg)
    S = f'[orange_red1] {" Ⓢ "} [/orange_red1]'
    B = f'[deep_sky_blue1] {" Ⓑ "} [/deep_sky_blue1]'
    
    orders = stub.FetchKiteOrders(req)
    table = Table(title=f"{msg} Kite Orders", box=box.HORIZONTALS)

    table.add_column("Order", justify="center", style="medium_purple3")
    table.add_column("Instrument", justify="center", style="light_steel_blue1")
    table.add_column("Price", justify="right", style="cyan")
    table.add_column("Product", justify="right", style="cyan")

    for order in orders:
        table.add_row(f"{datetime.fromtimestamp(order.ordertime.seconds).strftime('%H:%M:%S')}",
                    f"{order.quantity:2} {order.instrument.nicename:10} {flykite_pb2.Instrument.Exchange.Name(order.instrument.exchange):3}",
                    f"{B if flykite_pb2.OrderKite.Trade.Name(order.trade) == 'BUY' else S} {order.avgp5/20:>8.2f}",
                    f"{flykite_pb2.OrderKite.Product.Name(order.product)}")
    input_console.print(table)

def fetchIfThenElseOrders(stub:flykite_pb2_grpc.KiterStub,msg):
    req = flykite_pb2.KiteRequest(msg=msg)
    S = f'[orange_red1] Ⓢ [/orange_red1]'
    B = f'[deep_sky_blue1] Ⓑ [/deep_sky_blue1]'
    if msg == 'bs':
        msg = f'{B} [yellow]-[/yellow]{S} '
    elif msg == 'sb':
        msg = f'{S} [yellow]-[/yellow]{B} '

    orders = stub.FetchIfThenElseOrders(req)
    table = Table(title=f"{msg} ITE Orders", box=box.HORIZONTALS)

    table.add_column("Order", justify="center", style="medium_purple3")
    table.add_column("QtxSpl", justify="center", style="light_steel_blue1")
    table.add_column("Instrument", justify="center", style="light_steel_blue1")
    table.add_column("Enter", justify="right", style="cyan")
    table.add_column("Exit", justify="right", style="cyan")
    table.add_column("(Stop/No)loss", justify="right", style="cyan")
    table.add_column("P/L", justify="left", style="yellow")
    def symbolify(i):
        if i == flykite_pb2.OrderStatus.NOTSUBMITTED:
            return '⠀'
        elif i == flykite_pb2.OrderStatus.OPEN:
            return '☐'
        elif i == flykite_pb2.OrderStatus.COMPLETE:
            return '✔'
        elif i == flykite_pb2.OrderStatus.CANCELLED:
            return '☒'
        
    for order in orders:
        p5pl = 0
        color = 'yellow'
        if order.statusif == flykite_pb2.OrderStatus.COMPLETE and order.statusthen == flykite_pb2.OrderStatus.COMPLETE:
            p5pl = abs(order.p5if - order.p5then)
            color = 'green'
        if order.statusif == flykite_pb2.OrderStatus.COMPLETE and order.statuselse == flykite_pb2.OrderStatus.COMPLETE:
            p5pl = abs(order.p5if - order.p5else)
            if order.stoploss==True:
                color = 'red'
            else:
                color = 'green'
        pct = p5pl*100//order.p5if
        if pct == 0:
            pl = chr(9450)
        elif pct <= 20:
            pl = chr(9311+pct)
        elif pct <= 89:
            pl = chr(12871+pct//10)
        else:
            pl = chr(128128) if order.stoploss else chr(128175)
            


        table.add_row(f"{datetime.utcfromtimestamp(order.ordertime.seconds).strftime('%H:%M:%S')} {order.orderby}",
                    f"{order.quantity:03}x{order.split:02}",f"{order.instrument.nicename:10} {flykite_pb2.Instrument.Exchange.Name(order.instrument.exchange):3}",
                    f"{order.p5if/20:>8.2f}{symbolify(order.statusif):>2} {datetime.utcfromtimestamp(order.timeif.seconds).strftime('%H:%M:%S') if order.timeif.seconds>order.ordertime.seconds else ''}",
                    f"{order.p5then/20:>8.2f}{symbolify(order.statusthen):>2} {datetime.utcfromtimestamp(order.timethen.seconds).strftime('%H:%M:%S') if order.timethen.seconds>order.ordertime.seconds else ''}",
                    f"{order.p5else/20:>8.2f}{symbolify(order.statuselse):>2} {'SL' if order.stoploss else 'NL'} {' P' if order.papertrade else 'NP'} {datetime.utcfromtimestamp(order.timeelse.seconds).strftime('%H:%M:%S') if order.timeelse.seconds>order.ordertime.seconds else ''}",
                    f"[{color}]{pl:2}[/{color}]")
    input_console.print(table)
    

        
def submitIfThenElseOrder(stub:flykite_pb2_grpc.KiterStub, quantity, split, nicename, exchange, p5if, p5then, p5else, stoploss, papertrade):
    instrument = flykite_pb2.Instrument( nicename = nicename, exchange = flykite_pb2.Instrument.Exchange.NSE if exchange == 'NSE' else flykite_pb2.Instrument.Exchange.BSE)
    response = stub.SubmitIfThenElseOrder(flykite_pb2.OrderIfThenElse(instrument = instrument,
                                                                      quantity = quantity,
                                                                      split = split,
                                                                      p5if = p5if,
                                                                      p5then = p5then,
                                                                      p5else = p5else,
                                                                      stoploss = stoploss,
                                                                      papertrade = papertrade))
    input_console.print(response.msg)

def clearIfThenElseOrders(stub:flykite_pb2_grpc.KiterStub,msg):
    req = flykite_pb2.KiteRequest(msg=msg)
    response = stub.ClearIfThenElseOrders(req)
    input_console.print(response.msg)

def showDict(stub:flykite_pb2_grpc.KiterStub):
    response = stub.ShowDict(flykite_pb2.KiteRequest(msg = 'Request from InputClient'))
    input_console.print(response.msg)

def fetchCandles(stub:flykite_pb2_grpc.KiterStub, nicename, exchange):
    candlesticks = stub.FetchCandles(flykite_pb2.Instrument( nicename = nicename,
                            exchange = flykite_pb2.Instrument.Exchange.NSE if exchange == 'NSE' else flykite_pb2.Instrument.Exchange.BSE))
    if candlesticks:
        arr = np.empty((0,5),int)
        for candlestick in candlesticks:
            input_console.print(candlestick.p5high)
            if candlestick.p5high>0:
                arr = np.append(arr,np.array([[candlestick.p5high,candlestick.p5open,candlestick.p5close,candlestick.p5low,candlestick.volg]]),axis=0)
        # input_console.print(arr)
        df = pd.DataFrame(arr,columns=['h','o','c','l','v'])
        cc = CandleChart(df,32)
        if cc.df is not None:
            cc.draw()
    else:
        input_console.print('No candles.')


def displayHelp():
    input_console.print('submitIfThenElseOrder')
    input_console.print('/oisub 1*1 ADANIGREEN NSE 2845 2825 2850 sl np')
    input_console.print('/oisub 5*2 IEX NSE 186.90 185 190 nl p')
    input_console.print('fetchIfThenElseOrders')
    input_console.print('/oifet all')
    input_console.print('/oifet sb')
    input_console.print('/oifet bs')
    input_console.print('fetchKiteOrders')
    input_console.print('/kifet all')
    input_console.print('/kifet open')
    input_console.print('/kifet exec')
    input_console.print('clearIfThenElseOrders')
    input_console.print('/oiclr all')
    input_console.print('fetchCandles')
    input_console.print('/cdfet IEX NSE')
    input_console.print('showDict')
    input_console.print('/s')
    input_console.print('Update Flag to True')
    input_console.print('/cmdt kou')
    input_console.print('/cmdt exit')
    input_console.print('quit')
    input_console.print('/q')

def correctSyntax(argLst):
    if argLst[0] == '/oisub':
        if len(argLst) != 9:
            input_console.print('syntax')
        else:
            return True
    if argLst[0] == '/oifet':
        if len(argLst) == 1:
            argLst.append('all')
        return len(argLst) == 2
    if argLst[0] == '/oiclr':
        if len(argLst) == 1:
            argLst.append('all')
        return len(argLst) == 2
    if argLst[0] == '/cdfet':
        if len(argLst) != 3:
            input_console.print('syntax')
        else:
            return True
    if argLst[0] == '/kifet':
        if len(argLst) == 1:
            argLst.append('cmpl')
        return len(argLst) == 2
    if argLst[0] == '/cmdt':
        if len(argLst) != 2:
            input_console.print('syntax /cmdt [FLAG]')
        else:
            return True

if __name__ == '__main__':
    stub = flykite_pb2_grpc.KiterStub(grpc.insecure_channel('localhost:50051'))
    p5 = lambda rsstr : int(20*float(rsstr))
    while True:
        cmd = Prompt.ask("₹")
        argLst = cmd.split(sep=' ')
        if argLst[0] == '':
            input_console.print('')
        if argLst[0] == '/?':
            displayHelp()
                
        elif argLst[0] == '/s':
            showDict(stub)
        elif argLst[0] == '/oisub':
            if correctSyntax(argLst):
                submitIfThenElseOrder(stub,
                                      quantity= int(argLst[1].split('*')[0]),
                                      split = int(argLst[1].split('*')[1]), 
                                      nicename = argLst[2],
                                      exchange = argLst[3],
                                      p5if=p5(argLst[4]),
                                      p5then=p5(argLst[5]),
                                      p5else=p5(argLst[6]),
                                      stoploss=True if argLst[7].lower() == 'sl' else False,
                                      papertrade = True if argLst[8].lower() == 'p' else False)
        elif argLst[0] == '/oifet':
            if correctSyntax(argLst):
                fetchIfThenElseOrders(stub, msg = argLst[1])
        elif argLst[0] == '/oiclr':
            if correctSyntax(argLst):
                clearIfThenElseOrders(stub, msg = argLst[1])
        elif argLst[0] == '/cdfet':
            if correctSyntax(argLst):
                fetchCandles(stub, nicename = argLst[1], exchange = argLst[2])
        elif argLst[0] == '/kifet':
            if correctSyntax(argLst):
                fetchKiteOrders(stub, msg = argLst[1])
            
        elif argLst[0] == '/cmdt':
            if correctSyntax(argLst):
                command(stub, msg = argLst[1])
            
        
        elif cmd == 'data' or cmd == '/d':
            pass
        elif argLst[0] == '/q':
            exit()
            