from concurrent import futures
import multiprocessing as mp
import threading
import os
import sys
import math
import re
import time
import csv
import logging
from selenium import webdriver
from selenium.webdriver.chrome import service
from rich.logging import RichHandler
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support.wait import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from datetime import datetime,timedelta
from selenium.webdriver.common.keys import Keys
from common import Today
from mconfig import readConfig


class Kite():       

    def __init__(self,headless:bool,today:Today,ID=None,PASS=None,PIN=None):
        self.dict = {'hdl':{},'pos':{}}
        self.today = today
        if self.today.backtest == 0:
            self.driver = self.get_driver(headless)
            self.login(ID,PASS,PIN)
            self.original_window = self.driver.current_window_handle
            self.timetoReturnChart=False
        # self.holdings()

        self.path = os.path.dirname(os.path.realpath(__file__))
        
        FORMAT = "%(message)s"
        logging.basicConfig(
            level="INFO", format=FORMAT, datefmt="[%X]", handlers=[RichHandler(markup=True)]
        )
        
    def get_driver(self,headless):
        try:
            chrome_options = webdriver.ChromeOptions()
            chrome_options.add_argument('--disable-gpu')  
            if headless:
                chrome_options.add_argument('--headless')  
            chrome_options.add_argument("--window-size=1080,1920")
            chrome_options.add_argument('--start-maximized')
            chrome_options.add_argument("--disable-dev-shm-usage")
            if os.path.exists('/snap/bin/chromium.chromedriver'):
                svc = Service(executable_path='/snap/bin/chromium.chromedriver') 
            else:    
                quit()
            driver = webdriver.Chrome(
                service=svc,
                options=chrome_options
                )
            driver.get("https://kite.zerodha.com")
            if(driver.title!="Kite - Zerodha's fast and elegant flagship trading platform"):        
                quit()
            return driver
        except:
            print("Unknown error occurred while Opening")
    
    
    def login(self,ID,PASS,PIN):
        try:
            wait = WebDriverWait(self.driver, timeout=5)
            wait.until(EC.presence_of_element_located((By.XPATH,"//input[@id='userid']"))).send_keys(ID)
            wait.until(EC.presence_of_element_located((By.XPATH,"//input[@id='password']"))).send_keys(PASS)
            wait.until(EC.element_to_be_clickable((By.XPATH,"//button[contains(.,'Login')]"))).click()
            wait.until(EC.presence_of_element_located((By.XPATH,"//input[@label='Mobile App Code']"))).send_keys(PIN)
            wait.until(EC.element_to_be_clickable((By.XPATH,"//button[contains(.,'Continue')]"))).click()

            dash_div = wait.until(EC.presence_of_element_located((By.XPATH,"//div[@class='dashboard']//span[@class='nickname']/..")))
            if dash_div:
                self.welcome_msg = dash_div.text
                return True
        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            logging.error(f'{exc_type}, {fname}, {exc_tb.tb_lineno}')
            return False

    def instruments(self,watchlist=0):
        try:
            if self.today.backtest:
                for instrument in self.today.bt.instruLst:
                    p5 = self.today.currentp5(instrument)
                    yield (instrument,p5)
            else:
                wait = WebDriverWait(self.driver, timeout=5)
                if watchlist != 0:
                    wait.until(EC.element_to_be_clickable((By.XPATH,f"//ul[contains(@class,'marketwatch-selector')]//li[contains(.,'{watchlist}')]"))).click()
                if not wait.until(EC.presence_of_element_located((By.XPATH,"//div[@class='instruments']"))):
                    # print("Instruments could not be loaded successfully.")
                    return None
                if not len(self.driver.find_elements(By.XPATH,"//div[@class='instruments']//div[contains(@class,'vddl-list')]//div"))>0:
                    # print("Instruments empty.")
                    return None
                instrus = self.driver.find_elements(By.XPATH,"//div[@class='instruments']//div[@class='info']")
                if instrus:
                    for instru in instrus:
                        # self.data_dict['ins'][instru.text.partition('\n')[0].partition(' ')[0]]=instru.text.rpartition('\n')[2].partition(' ')[0]
                        nicename=instru.text.partition('\n')[0].partition(' ')[0]
                        exchange='BSE' if instru.text.partition('\n')[0].partition(' ')[2]=='BSE' else 'NSE'
                        instrument = f'{nicename}.{exchange[0]}'
                        price_str=instru.text.rpartition('\n')[2].rpartition(' ')[2]
                        # some time data loads late, so just to make sure this is the intended value
                        if '.' in price_str:
                            p5=int(20*float(price_str))
                            # self.data_dict['ins'][f'{watchlist}'][f'{name}.{exchange}']=value
                            yield (instrument,p5)
                # return self.data_dict['ins'][f'{watchlist}']
        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            logging.error(f'{exc_type}, {fname}, {exc_tb.tb_lineno}')
            return None
            
    def trade(self,nicename:str,p5:int,quantity=1,tradetype='Buy',producttype='MIS',exchange='NSE',atprice='Market',papertrade=True):
        try:
            if self.today.backtest:
                self.today.sleep(1)
            else:
                wait = WebDriverWait(self.driver, timeout=5)
                actions = ActionChains(self.driver)
                visibleDiv=wait.until(EC.presence_of_element_located((By.XPATH,f"//div[contains(@class,'info') and contains(.,'{nicename.upper()}')]")))
                if visibleDiv:
                    actions.move_to_element(visibleDiv)
                    actions.perform()
                    actions.pause(0.2)
                if tradetype:
                    hiddenElem=wait.until(EC.presence_of_element_located((By.XPATH,f"//button[contains(@class,'{tradetype.lower()}')]")))
                    # actions.move_to_element(hiddenElem)
                    actions.click(hiddenElem)
                    actions.perform()
                    actions.pause(0.2)
                assert self.driver.find_element(By.XPATH,"//div[@class='instrument']//span[@class='name']").text == nicename
                assert self.driver.find_element(By.XPATH,"//div[@class='instrument']//span[@class='transaction-type']").text == tradetype
                if exchange:
                    exchangeElem=wait.until(EC.presence_of_element_located((By.XPATH,f"//form//input[@value='{exchange}']")))
                    # actions.move_to_element(exchangeElem)
                    actions.click(exchangeElem)
                    actions.perform()
                    actions.pause(0.2)
                assert self.driver.find_element(By.XPATH,"//div[@class='instrument']//span[@class='exchange']").text == exchange
                if producttype:
                    prodElem=wait.until(EC.presence_of_element_located((By.XPATH,f"//form//input[@value='{producttype}']//parent::div")))
                    # actions.move_to_element(prodElem)
                    actions.click(prodElem)
                    actions.perform()
                    actions.pause(0.2)
                if atprice:
                    marketElem=wait.until(EC.presence_of_element_located((By.XPATH,f"//form//input[@label='{atprice}']")))
                    # actions.move_to_element(marketElem)
                    actions.click(marketElem)
                    actions.perform()
                    actions.pause(0.2)
                    if atprice == 'Limit':
                        input_elem=wait.until(EC.presence_of_element_located((By.XPATH,"//div[contains(@class,'price')]//input[@type='number']")))
                        input_elem.clear()
                        input_elem.send_keys(p5/20)
                if quantity>0:
                    wait.until(EC.presence_of_element_located((By.XPATH,"//div[contains(@class,'quantity')]//input[@type='number']"))).send_keys(quantity)
                if tradetype:
                    if papertrade:
                        wait.until(EC.element_to_be_clickable((By.XPATH,f"//form//button[contains(.,'Cancel')]"))).click()
                    else:
                        wait.until(EC.element_to_be_clickable((By.XPATH,f"//form//button[contains(.,'{tradetype}')]"))).click()
                        # shortTermSpan=wait.until(EC.presence_of_element_located((By.XPATH,f"//div[contains(@class,'order-toast')]//span[@class='order-id']")))
                        # if shortTermSpan:
                        #     return shortTermSpan.text
            if f'{nicename}.{exchange[0]}' not in self.dict['pos'].keys():
                self.dict['pos'][f'{nicename}.{exchange[0]}']=0
            self.dict['pos'][f'{nicename}.{exchange[0]}'] += quantity if tradetype == 'Buy' else -quantity
            exectime = self.today.now()
            logging.info(f'{exectime:%H:%M:%S} {"Backtest" if self.today.backtest>0 else "Paper" if papertrade else "Actual"} {quantity:02} {nicename:10} {exchange} {p5/20:{20 if tradetype=="Buy" else 10}.2f}{"~" if atprice=="Market" else " "} POS {self.dict["pos"][f"{nicename}.{exchange[0]}"]}')
            return exectime
        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            logging.error(f'{exc_type}, {fname}, {exc_tb.tb_lineno}')
            return None
        
    
    def positions(self):
        try:
            wait = WebDriverWait(self.driver, timeout=5)
            if self.driver.title != 'Positions / Kite':
                wait.until(EC.element_to_be_clickable((By.XPATH,"//div[@class='app-nav']//a[contains(.,'Positions')]"))).click()
            

            if not wait.until(EC.presence_of_element_located((By.XPATH,"//div[@class='positions']"))):
                print("Page could not load successfully.")
                return None
            if self.driver.find_element(By.XPATH,"//div[@class='positions']//div[@class='empty-state']"):
                return None
            pos_header = self.driver.find_element(By.XPATH,"//div[@class='positions']//section[contains(@class,'open-positions')]//header")
            
            if pos_header:
                self.dict['kpos'] = { 'h1':pos_header.text }
            pos_data_table = self.driver.find_element(By.XPATH,"//div[@class='positions']//section[contains(@class,'open-positions')]//table")
            if pos_data_table:
                #check how it was working previously all rows or only selected???
                h = self.driver.find_element(By.XPATH,'//tbody//tr')
                # print (h.text)
                
                for r in self.driver.find_elements(By.XPATH,'//tbody//tr'):
                    # r.text = 'MIS BANKBARODA NSE 3 85.35 84.80 -1.65 -0.64%'
                    #use regex
                    # print(r.text)
                    self.dict['kpos']= {'p1':r.text,'p2':'greatt!'}
            return self.dict['kpos']
        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            logging.error(f'{exc_type}, {fname}, {exc_tb.tb_lineno}')
            return None

    def holdings(self):
        try:
            if self.today.backtest:
                for instrument in self.today.bt.instruLst:
                    p5 = self.today.currentp5(instrument)
                    self.dict['hdl'][instrument]=(5,100,95,-10,-5)
            else:
                wait = WebDriverWait(self.driver, timeout=5)
                if self.driver.title != 'Holdings / Kite':
                    wait.until(EC.element_to_be_clickable((By.XPATH,"//div[@class='app-nav']//a[contains(.,'Holdings')]"))).click()
                holding_rows = wait.until(EC.presence_of_all_elements_located((By.XPATH,f"//div[@class='holdings']//table/tbody/tr")))
                def val(dname):
                    data = lambda dnum: row.find_elements(By.TAG_NAME,'td')[dnum].text
                    if dname == 'instrument':
                        return f'{data(0)}.N'
                    elif dname == 'quantity':
                        lstD = data(1).split(' ')
                        if len(lstD) == 1:
                            return int(lstD[0])
                        else:
                            return int(lstD[1]) + int(lstD[2])
                    elif dname == 'avg':
                        return float(data(2).replace(',',''))
                    elif dname == 'ltp':
                        return float(data(3).replace(',',''))
                    elif dname == 'total':
                        return float(data(4).replace(',',''))
                    elif dname == 'tpchange':
                        return float(data(5).replace('%',''))
                    elif dname == 'dpchange':
                        return float(data(6).replace('%',''))
                for row in holding_rows:
                    round((val('quantity')*val('ltp')),2)==val('total')
                    #To be fixed
                    self.dict['hdl'][val('instrument')]=(val('quantity'),val('avg'),val('ltp'),val('tpchange'),val('dpchange'))
        except:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            logging.error(f'{exc_type}, {fname}, {exc_tb.tb_lineno}')
            return None

    def orders(self,ordertype=None):
        try:
            wait = WebDriverWait(self.driver, timeout=5)
            if self.driver.title != 'Orders / Kite':
                wait.until(EC.element_to_be_clickable((By.XPATH,"//div[@class='app-nav']//a[contains(.,'Orders')]"))).click()
            if not ordertype:
                return
        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            logging.error(f'{exc_type}, {fname}, {exc_tb.tb_lineno}')
            return None
        
        try:
            order_rows = wait.until(EC.presence_of_all_elements_located((By.XPATH,f"//div[@class='{ordertype}-orders']//table/tbody/tr")))
            text = lambda cname: row.find_element(By.CLASS_NAME,cname).text
            for row in order_rows:
                # print(row.text)
                yield (text('order-timestamp'),text('transaction-type'),text('tradingsymbol'),text('exchange'),text('product'),
                text('quantity'),text('average-price'),text('order-status'))
        except:
            return None


    def dashboard(self):
        try:
            wait = WebDriverWait(self.driver, timeout=5)
            if self.driver.title != 'Dashboard / Kite':
                wait.until(EC.element_to_be_clickable((By.XPATH,"//div[@class='app-nav']//a[contains(.,'Dashboard')]"))).click()
            
            dash_div = wait.until(EC.presence_of_element_located((By.XPATH,"//div[@class='dashboard']//span[@class='nickname']/..")))
            if dash_div:
                self.welcome_msg = dash_div.text
            
            label0 = self.driver.find_elements(By.XPATH,"//div[contains(@class,'primary-stats')]//div[@class='label']")[0].text
            value0 = self.driver.find_elements(By.XPATH,"//div[contains(@class,'primary-stats')]//div[@class='value']")[0].text
            
            label1 = self.driver.find_elements(By.XPATH,"//div[contains(@class,'secondary-stats')]//span[@class='label']")[0].text
            value1 = self.driver.find_elements(By.XPATH,"//div[contains(@class,'secondary-stats')]//span[@class='value']")[0].text
            
            label2 = self.driver.find_elements(By.XPATH,"//div[contains(@class,'secondary-stats')]//span[@class='label']")[1].text
            value2 = self.driver.find_elements(By.XPATH,"//div[contains(@class,'secondary-stats')]//span[@class='value']")[1].text
            
            self.dict['dsh']= {label0: value0,label1: value1,label2: value2}
            return self.dict['dsh']
        except:
            print("Unknown error occurred while Fetching Dashboard")
            return None
            
    def fetchchartdata(self,instrument:str,interval:str,extern:bool=False):
        try:
            nicename=instrument.split('.')[0].upper()
            exchange=f"{instrument.split('.')[1].upper()}SE"
            wait = WebDriverWait(self.driver, timeout=5)
            actions = ActionChains(self.driver)
            
            if extern:
                if nicename=='ADANIGREEN':
                    cid=912129
                if nicename=='BANKBARODA':
                    cid=1195009
                
                self.driver.get(f"https://kite.zerodha.com/chart/ext/ciq/{exchange}/{nicename}/{cid}")
                self.driver.switch_to.frame('chart-iframe')
            else:
                self.driver.switch_to.window(self.original_window)
                if f"{nicename} ({exchange})" not in self.driver.title:
                    visibleDiv=wait.until(EC.presence_of_element_located((By.XPATH,f"//div[contains(@class,'info') and contains(.,'{nicename}')]")))
                    if visibleDiv:
                        actions.move_to_element(visibleDiv)
                        actions.perform()
                        actions.pause(0.2)
                        hiddenElem=wait.until(EC.presence_of_element_located((By.XPATH,f"//span[@data-balloon='Chart (C)']/button")))
                        # actions.move_to_element(hiddenElem)
                        actions.click(hiddenElem)
                        actions.perform()
                        actions.pause(0.2)
                    self.driver.switch_to.frame('chart-iframe')
            assert f"{nicename} ({exchange})" in self.driver.title
            # self.driver.get(f"https://kite.zerodha.com/chart/ext/ciq/{exchange}/{nicename}/{cid}")
            # self.driver.switch_to.frame('chart-iframe')
            logging.info('slept')
            time.sleep(5)
            elm = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR,".ciq-period")))
            # chart preferences must be saved with required settings
            if (elm.text != interval):
                logging.info(f"Period should be of {interval}. Its {elm.text} at present.")
                return
            elif interval=='1m':
                tmfmt = "%d/%m/%Y %H:%M"
            elif interval=='1D':
                tmfmt = "%d/%m/%Y"
            m5=1
            current=True
            elem=wait.until(EC.presence_of_element_located((By.XPATH,"//div[contains(@class,'chartContainer')]")))
            actions.pause(0.2)
            logging.info('+624')
            actions.drag_and_drop_by_offset(elem, 208, 0).perform()
            actions.drag_and_drop_by_offset(elem, 208, 0).perform()
            actions.drag_and_drop_by_offset(elem, 208, 0).perform()
            actions.pause(1.2)
            # actions.drag_and_drop_by_offset(elem, 208, 0).perform()
            # actions.pause(0.2)
            homeDiv = wait.until(EC.presence_of_element_located((By.XPATH,f"//div[contains(@class,'stx_jump_today')]")))
            if homeDiv:
                actions.click(homeDiv)
                actions.pause(1.2)
            # actions.pause(0.2)
            # logging.info('-416')
            # actions.drag_and_drop_by_offset(elem, -416, 0).perform()
            actions.pause(0.2)
            logging.info('-416')
            actions.drag_and_drop_by_offset(elem, -416, 0).perform()
            actions.pause(1.2)
            # actions.drag_and_drop_by_offset(elem, -216, 0).perform()
            # actions.pause(1.2)

            # time.sleep(2)
            # actions.move_by_offset(100,100).perform()
            #actions.perform()
            xx=16 # this is the width of one column
            xx=8
            xxff = 600
            yy=0
            prev = ''
            latest=True
            while True:
                #actions.move_by_offset(xx,yy)
                #actions.perform()
                elem=wait.until(EC.presence_of_element_located((By.XPATH,"//div[contains(@class,'chartContainer')]")))
                actions.drag_and_drop_by_offset(elem, xx, yy).perform()
                par = WebDriverWait(self.driver, timeout=5).until(EC.presence_of_element_located((By.XPATH,"//cq-hu-dynamic")))
                if par.text == '':
                    logging.info('skipped empty.')
                    continue
                elif prev == par.text:
                    logging.info('repeatition reverse move two and half.')
                    actions.drag_and_drop_by_offset(elem, -int(xx*2.5), yy).perform()
                    continue
                prev = par.text
                # print(par.text)
                result = re.split('\n', par.text)
                #Check if the text block is in right format
                if not len(result)==12:
                    raise Exception('Text block format seems wrong.')
                elif result[2]=='VOLUME' and result[4]=='OPEN' and result[6]=='CLOSE' and result[8]=='HIGH' and result[10]=='LOW':
                    str_dt = result[0]
                    def amount(str_rs):
                        return int(float(str_rs))
                    def p5(str_rs):
                        return int(float(str_rs)*100)//5
                    
                    
                    def dayofyear():
                        if int(datetime.strptime(str_dt, tmfmt).strftime(f"%Y")) != 2022:
                            return 0
                        # return datetime.strptime(str_dt, tmfmt).strftime(f"%Y-%m-%d %H:%M")
                        else:
                            return datetime.strptime(str_dt, tmfmt).timetuple().tm_yday
                    def hourofday():
                        # return datetime.strptime(str_dt, tmfmt).strftime(f"%Y-%m-%d %H:%M")
                        return datetime.strptime(str_dt, tmfmt).hour-12
                    def hour():
                        return datetime.strptime(str_dt, tmfmt).hour
                    def minute():
                        return datetime.strptime(str_dt, tmfmt).minute
                    monthval = lambda : int(datetime.strptime(str_dt, tmfmt).strftime(f"%-m"))
                    dayval = lambda : int(datetime.strptime(str_dt, tmfmt).strftime(f"%-d"))
                    datetimeval = lambda : datetime.strptime(str_dt, tmfmt)
                    monthname =  lambda : datetime.strptime(str_dt, tmfmt).strftime(f"%b")
                    def lg(str_vol):
                        if str_vol.isdecimal():
                            if int(str_vol) == 0:
                                return 1    #not returning zero to differentiate b/w complete and incomplete data
                            else:
                                return math.floor(math.log2(int(str_vol)))+1
                        elif str_vol.endswith('K'):
                            return math.floor(math.log2(float(str_vol[:-1])*1000))+1
                        elif str_vol.endswith('M'):
                            return math.floor(math.log2(float(str_vol[:-1])*1000000))+1
                        
                    hr = hour()
                    min = minute()
                    
                    doy = dayofyear()
                    #Fast forward if needed
                    # if monthval()>month and dayval() > 1:
                    #     actions.drag_and_drop_by_offset(elem, xxff, yy).perform()
                    #     print(f'fastforwarded {datetimeval()}')
                    #     continue
                    
                    # if monthval()==month+1:
                    #     print(f'skipped {datetimeval()}')
                    #     continue

                    # price = amount(result[1])
                    v = lg(result[3])
                    o = p5(result[5])
                    c = p5(result[7])
                    h = p5(result[9])
                    l = p5(result[11])
                    
                    
                    if interval == '1m':
                        mm=((hr-9)*60+min-15)//m5
                        if self.today.init.timetuple().tm_yday != datetimeval().timetuple().tm_yday:
                            current=False
                    elif interval == '1D':
                        mm=datetimeval().timetuple().tm_yday
                        if self.today.init.timetuple().tm_year != datetimeval().timetuple().tm_year:
                            current=False
                    if self.timetoReturnChart or not current:
                        logging.info('+624')
                        actions.drag_and_drop_by_offset(elem, 208, 0).perform()
                        actions.drag_and_drop_by_offset(elem, 208, 0).perform()
                        actions.drag_and_drop_by_offset(elem, 208, 0).perform()
                        actions.pause(1.2)
                        return
                    if latest:
                        logging.info(f"skipping {monthname()} {dayval():02} - {hr:02}:{min:02} -> {nicename} {exchange}")
                        latest=False
                    else:
                        logging.info(f"yielding {monthname()} {dayval():02} - {hr:02}:{min:02} -> {nicename} {exchange} : {mm} -> v {v} o {o} c {c} h {h} l {l}")
                        yield(mm,h,o,c,l,v)

        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            logging.error(f'{exc_type}, {fname}, {exc_tb.tb_lineno}')
            return None
    def OpenChart(self):
        try:
            self.driver.get('http://google.com')
            time.sleep(10)
            # self.driver.switch_to.new_window('tab')
        except Exception as e:
            exc_type, exc_obj, exc_tb = sys.exc_info()
            fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
            logging.error(f'{exc_type}, {fname}, {exc_tb.tb_lineno}')
            return None


def kitelogin(headless):
    kite = None
    today = Today(0)
    kLogins=readConfig('kites')
    if kLogins:
        kite = Kite(headless,today, kLogins[1]['zId'], kLogins[1]['zPass'], kLogins[1]['zPin'])
        if kite:
            return kite


def ADN(kite:Kite):
    for item in kite.fetchchartdata('ADANIGREEN.N','1m',True):
        logging.info(item)
def BOB(kite:Kite):
    for item in kite.fetchchartdata('BANKBARODA.N','1m',True):
        logging.info(item)
def Tab(kite:Kite):
    try:
        logging.info('hello')
        kite.OpenChart()
    except Exception as e:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        logging.error(f'{exc_type}, {fname}, {exc_tb.tb_lineno}')
        return None

def ChartThreads(headless:bool):
    try:
        logging.info('here')
        
        kite = kitelogin(headless)
        body=kite.driver.find_element(By.TAG_NAME,"body")
        body.send_keys(Keys.CONTROL,'t')
        time.sleep(10)
        # tL.append(threading.Thread(target=ADN, args=(kite)))
        # t=threading.Thread(target=Tab, args=(kite))
        # for t in tL:
        # t.start()
        # for t in tL:
        # t.join()
        # tL[1].join()
    except Exception as e:
        exc_type, exc_obj, exc_tb = sys.exc_info()
        fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
        logging.error(f'{exc_type}, {fname}, {exc_tb.tb_lineno}')
        return None
    


if __name__ == '__main__':


    
    # def saveData(nicename,exchange,month):
    #     try:
    #         with open(os.path.join(kite.path, "data", "chart.csv"), mode='r') as csvfile:
    #             reader = csv.DictReader(csvfile)
    #             found = False
    #             for row in reader:
    #                 if nicename == row['nicename']:
    #                     cid = row[f'{exchange}cid']
    #                     instrument=f"{nicename}.{exchange[0]}"
    #                     found = True
    #                     break
    #             if found:
    #                 list(kite.savechartdata(instrument,'1m'))
    #             else:
    #                 print('cid info not found.')
    #     except:
    #         exc_type, exc_obj, exc_tb = sys.exc_info()
    #         fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
    #         logging.error(f'{exc_type}, {fname}, {exc_tb.tb_lineno}')
    #         return None

    # def showOrders(ordertype):
    #     gen = kite.orders(ordertype)
    #     # print(gen)
    #     for i in gen:
    #         print(i)



    headless=False #if input('headless: ')=='y' else False
    jobs = []
    
    with mp.Pool() as pool:
        jobs.append(pool.apply_async(ChartThreads, [headless]))
        # jobs.append(pool.apply_async(ADN, [kite]))
        # jobs.append(pool.apply_async(BOB, [kite]))
        while True:
            if input()=='exit':
                exit()
    # print(kite.dict['hdl'])
    # kite.orders()
    # nicename = input('nicename: ').upper()
    # exchange = input('exchange: ').upper()
    # month = int(input('month: '))
    # saveData(nicename, exchange, month)
    # showOrders('open')
    # showOrders('open')
    # showOrders('completed')
    # showOrders('open')
    # showOrders('completed')
