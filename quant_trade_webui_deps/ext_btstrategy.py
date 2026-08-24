from .common_utils import *
import backtrader as bt


class ExtBtStrategy(bt.Strategy):
    """
    backtrader标准策略类基础上封装基类
    用于添加一些本框架额外定义的功能
    目前加了些交易统计信息


    """

    def __init__(self, dataframe_plotters=[]):
        self.dataframe_plotters = dataframe_plotters
        self.trade_history = {}
        self.tradeid_to_ref = {}

        # 保存子类原始的 notify_trade
        original_notify_order = self.notify_order

        # 检查是否子类重写了 notify_trade
        if original_notify_order != ExtBtStrategy.notify_order:
            self._user_notify_order = original_notify_order
        else:
            self._user_notify_order = None

        # 替换实例方法notify_order，这样可以保证用户如果也定义了notify_order也会正常运行
        self.notify_order = self._wrapped_notify_order.__get__(self, ExtBtStrategy)

    # 拓展基类在notify_order回调中，记录每笔交易详情
    def _wrapped_notify_order(self, order: bt.order.Order):
        if order.status == order.Completed:
            self.trade_history[order.ref] = {
                "交易对象": order.data._name,
                "交易价格": order.executed.price,
                "交易时间": self.datas[0].datetime.datetime(0),
                "交易股数": order.executed.size,
                "交易收益": order.executed.pnl,
                "剩余持仓": self.getposition(order.data).size,
                "账户资产": self.broker.getvalue(),
            }
        if self._user_notify_order:
            self._user_notify_order(order)
