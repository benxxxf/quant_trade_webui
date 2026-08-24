import backtrader as bt
from quant_trade_webui_deps.ext_btstrategy import *

class StrategyExample0(ExtBtStrategy):
    """
    单股双均线策略示范：金叉买入，死叉卖出
    """
    params = (
        ('fast', 5),  
        ('slow', 20),  
        ('print_flag',False)
    )

    def __init__(self,dataframe_plotters=[]):
        super().__init__(dataframe_plotters)
        self.fast_ma = bt.indicators.SMA(self.datas[0].close, period=self.params.fast)
        self.slow_ma = bt.indicators.SMA(self.datas[0].close, period=self.params.slow)
        self.crossover = bt.indicators.CrossOver(self.fast_ma, self.slow_ma)

    def next(self):
        pos0 = self.getposition(self.datas[0]).size
        if pos0==0 and self.crossover > 0:
            self.params.print_flag and print(f"'{self.datas[0]._name}'触发买入信号")
            cash_acc=self.broker.get_cash()
            buy_size = int(cash_acc*0.6 // self.datas[0].close[0] // 100 * 100) 
            self.buy(data=self.datas[0],size=buy_size)
        elif pos0 > 0 and self.crossover < 0:
            self.params.print_flag and print(f"'{self.datas[0]._name}'触发卖出信号")
            cur_pos = self.getposition(self.datas[0]).size
            self.sell(data=self.datas[0],size=cur_pos)