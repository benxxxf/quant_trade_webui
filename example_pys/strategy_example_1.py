import backtrader as bt
from quant_trade_webui_deps.ext_btstrategy import *


class StrategyExample1(ExtBtStrategy):
    """
    双股双均线策略示范：金叉买入，死叉卖出
    """

    params = (
        ("fast", 10),
        ("slow", 30),
        ("print_flag", False),
    )

    def __init__(self, dataframe_plotters=[]):
        super().__init__(dataframe_plotters)
        self.fast_ma_0 = bt.indicators.SMA(self.datas[0].close, period=self.params.fast)
        self.slow_ma_0 = bt.indicators.SMA(self.datas[0].close, period=self.params.slow)
        self.crossover_0 = bt.indicators.CrossOver(self.fast_ma_0, self.slow_ma_0)

        self.fast_ma_1 = bt.indicators.SMA(self.datas[1].close, period=self.params.fast)
        self.slow_ma_1 = bt.indicators.SMA(self.datas[1].close, period=self.params.slow)
        self.crossover_1 = bt.indicators.CrossOver(self.fast_ma_1, self.slow_ma_1)

    def next(self):
        pos0 = self.getposition(self.datas[0]).size
        cash_acc = self.broker.get_cash()
        if pos0 == 0 and self.crossover_0 > 0:
            self.params.print_flag and print(f"'{self.datas[0]._name}'触发买入信号")

            buy_size = int(cash_acc * 0.6 // self.datas[0].close[0] // 100 * 100)
            self.buy(data=self.datas[0], size=buy_size)
            cash_acc -= buy_size * self.datas[0].close[0]
        elif pos0 > 0 and self.crossover_0 < 0:
            self.params.print_flag and print(f"'{self.datas[0]._name}'触发卖出信号")
            cur_pos = self.getposition(self.datas[0]).size
            self.sell(data=self.datas[0], size=cur_pos)

        pos1 = self.getposition(self.datas[1]).size
        if pos1 == 0 and self.crossover_1 > 0:
            self.params.print_flag and print(f"'{self.datas[1]._name}'触发买入信号")
            buy_size = int(cash_acc * 0.6 // self.datas[1].close[0] // 100 * 100)
            self.buy(data=self.datas[1], size=buy_size)
        elif pos1 > 0 and self.crossover_1 < 0:
            self.params.print_flag and print(f"'{self.datas[1]._name}'触发卖出信号")
            cur_pos = self.getposition(self.datas[1]).size
            self.sell(data=self.datas[1], size=cur_pos)

