import pandas as pd
import json
from pathlib import Path
import os
from decimal import Decimal
from datetime import datetime, timedelta
import hashlib
from typing import Union, List,Optional
import copy
import tkinter as tk
from tkinter import filedialog
import tempfile
import streamlit as st
import sys
from enum import Enum
import numpy as np
import talib
from numba import jit
from abc import ABC, abstractmethod
import time




def infer_time_unit(
    time_data: Union[pd.Series, pd.Index, pd.DatetimeIndex, pd.DataFrame, list],
    time_col: Optional[str] = None
) -> str:
    """
    推断时间序列中最常见的时间间隔单位。

    支持从时间索引、时间列、时间字符串列表或单个时间值中提取时间信息，
    并根据时间戳之间的主要间隔返回对应的中文单位。

    Args:
        time_data: 时间数据，支持多种类型：
            - pd.Series: 时间戳列
            - pd.Index / pd.DatetimeIndex: 时间索引
            - pd.DataFrame: DataFrame，需要通过 time_col 指定列名
            - list: 时间字符串列表
        time_col: 当 time_data 为 DataFrame 时，指定时间列名
        
    Returns:
        str: '年' | '月' | '周' | '日' | '时' | '分' | '秒' | '未知'
    """
    # ========== 1. 提取时间序列 ==========
    date_series = None
    
    # 情况1: 传入的是 DataFrame
    if isinstance(time_data, pd.DataFrame):
        if time_col is not None and time_col in time_data.columns:
            # 使用指定的列
            date_series = time_data[time_col]
        else:
            # 尝试使用索引
            date_series = time_data.index.to_series()
    
    # 情况2: 传入的是 Index (包括 DatetimeIndex)
    elif isinstance(time_data, pd.Index):
        date_series = time_data.to_series()
    
    # 情况3: 传入的是 Series
    elif isinstance(time_data, pd.Series):
        date_series = time_data
    
    # 情况4: 传入的是列表
    elif isinstance(time_data, list):
        date_series = pd.Series(time_data)
    
    # 情况5: 传入的是单个时间戳
    else:
        try:
            date_series = pd.Series([time_data])
        except:
            return "未知"
    
    # ========== 2. 数据清洗 ==========
    # 确保是 datetime 类型
    try:
        date_series = pd.to_datetime(date_series)
    except Exception as e:
        return "未知"
    
    # 去除空值、排序、去重
    date_series = date_series.dropna().sort_values().drop_duplicates()
    
    if len(date_series) < 2:
        return "未知"
    
    # ========== 3. 计算时间间隔 ==========
    diffs = date_series.diff().dropna()
    if len(diffs) == 0:
        return "未知"
    
    # 转换为秒数
    diff_seconds = diffs.dt.total_seconds()
    # 过滤掉异常值（0或负数）
    diff_seconds = diff_seconds[diff_seconds > 0]
    
    if len(diff_seconds) == 0:
        return "未知"
    
    # ========== 4. 获取主要间隔 ==========
    # 使用众数（最常见的间隔）
    mode_sec = diff_seconds.mode().iloc[0]
    
    # 如果众数不唯一，尝试使用中位数
    if diff_seconds.mode().shape[0] > 1:
        mode_sec = diff_seconds.median()
    
    # 或者使用平均值（如果数据均匀）
    # mode_sec = diff_seconds.mean()
    
    mode_sec = round(mode_sec, 2)
    
    # ========== 5. 判断时间单位 ==========
    DAY_SEC = 24 * 3600
    MONTH_SEC_MIN = 28 * DAY_SEC
    MONTH_SEC_MAX = 31 * DAY_SEC
    YEAR_SEC = 365 * DAY_SEC
    
    # 优先判断特殊单位
    if mode_sec >= YEAR_SEC * 0.9 and mode_sec <= YEAR_SEC * 1.1:
        return "年"
    elif mode_sec >= MONTH_SEC_MIN and mode_sec <= MONTH_SEC_MAX:
        return "月"
    elif abs(mode_sec - 7 * DAY_SEC) < 0.5 * DAY_SEC:
        return "周"
    elif mode_sec >= 0.8 * DAY_SEC and mode_sec <= 1.2 * DAY_SEC:
        return "日"
    elif mode_sec >= 0.8 * 3600 and mode_sec <= 1.2 * 3600:
        return "时"
    elif mode_sec >= 0.8 * 60 and mode_sec <= 1.2 * 60:
        return "分"
    elif mode_sec < 0.8:
        return "秒"
    
    # ========== 6. 处理混合或不规则间隔 ==========
    # 检查变异系数，判断是否均匀
    cv = diff_seconds.std() / diff_seconds.mean() if diff_seconds.mean() > 0 else 1
    
    if cv > 0.5:
        # 如果不均匀，尝试找到最常见的间隔
        # 对间隔进行分组
        rounded = diff_seconds.round()
        if len(rounded.unique()) <= 2:
            # 如果只有少数几种间隔，可能是混合数据
            return "混合"
        else:
            return "不规则"
    
    # 如果没有匹配到任何已知单位，返回具体秒数
    return f"{int(mode_sec)}秒"
    
def string_to_rgb(s: str) -> str:
    """
    将任意字符串转换为稳定的 RGB 颜色字符串。

    同一个字符串始终生成相同的颜色，不同字符串则根据其 MD5 哈希值生成颜色。

    Args:
        s (str): 用于生成颜色的输入字符串。

    Returns:
        str: CSS 格式的 RGB 颜色字符串，例如 ``rgb(12, 34, 56)``。
    """
    hash_obj = hashlib.md5(s.encode('utf-8'))
    hex_digest = hash_obj.hexdigest()
    
    # ✅ 用整个哈希值计算 RGB，分散度更高
    # 将 32 位十六进制分成 3 份
    part_size = len(hex_digest) // 3
    r_hex = hex_digest[0:part_size]
    g_hex = hex_digest[part_size:part_size*2] 
    b_hex = hex_digest[part_size*2:]
    
    # 将每部分转为 0-255
    r = int(r_hex, 16) % 256
    g = int(g_hex, 16) % 256
    b = int(b_hex, 16) % 256
    
    return f'rgb({r}, {g}, {b})'

def parse_date_flexible(date_str: str) -> pd.Timestamp:
    """
    灵活解析多种常见日期格式。

    函数会依次尝试预设日期格式，全部失败后再交由 Pandas 自动解析。

    Args:
        date_str (str): 待解析的日期字符串。支持日期、日期时间、斜杠日期、
            紧凑日期以及中文日期等格式。

    Returns:
        pd.Timestamp: 解析后的时间戳；输入为空时返回 None。

    Raises:
        ValueError: 输入内容无法被支持的格式解析时抛出。
    """
    if not date_str:
        return None
    
    date_str = str(date_str).strip()
    
    # 尝试多种格式
    formats = [
        '%Y-%m-%d',           # 2024-01-01
        '%Y-%m-%d %H:%M:%S',  # 2024-01-01 00:00:00
        '%Y/%m/%d',           # 2024/01/01
        '%Y%m%d',             # 20240101
        '%Y-%m-%dT%H:%M:%S',  # 2024-01-01T00:00:00
        '%d-%m-%Y',           # 01-01-2024
        '%d/%m/%Y',           # 01/01/2024
        '%Y年%m月%d日',        # 2024年01月01日
    ]
    
    for fmt in formats:
        try:
            return pd.to_datetime(date_str, format=fmt)
        except:
            continue
    
    # 如果所有格式都失败，让 pandas 尝试自动解析
    try:
        return pd.to_datetime(date_str)
    except:
        raise ValueError(f"无法解析日期格式: '{date_str}'。支持的格式包括: YYYY-MM-DD, YYYYMMDD, YYYY/MM/DD 等")


def filter_dfs_by_time_range(
    df: Union[pd.Series, List[pd.Series], pd.DataFrame, List[pd.DataFrame]], 
    date_start: str = "", 
    date_end: str = "",
):
    """
    按时间范围筛选数据（支持 Series、DataFrame 及其列表）
    
    Args:
    - df: Series、DataFrame 或它们的列表
    - date_start: 开始时间
    - date_end: 结束时间
    
    支持的日期格式:
    - YYYY-MM-DD (2024-01-01)
    - YYYYMMDD (20240101)
    - YYYY/MM/DD (2024/01/01)
    - YYYY-MM-DD HH:MM:SS (2024-01-01 00:00:00)
    - 以及其他常见格式
    
    Returns:
    - 与原输入类型相同的筛选后数据
    """
    # 处理时间范围
    if date_start != "":
        time_start =parse_date_flexible(date_start)
    else:
        time_start = pd.Timestamp("1970-01-01")
    
    if date_end != "":
        time_end = parse_date_flexible(date_end)
    else:
        time_end = pd.Timestamp.now()
    
    def _filter_single(data: Union[pd.Series, pd.DataFrame]) -> Union[pd.Series, pd.DataFrame]:
        """
        筛选单个 Series 或 DataFrame。

        Args:
            data (Union[pd.Series, pd.DataFrame]): 待筛选的数据对象。

        Returns:
            Union[pd.Series, pd.DataFrame]: 时间范围内的数据对象。

        Raises:
            ValueError: 数据索引不是 ``pd.DatetimeIndex`` 时抛出。
        """
        
        # 情况1: 时间在索引中
        if isinstance(data.index, pd.DatetimeIndex):
            return data.loc[time_start:time_end]
        
        else:
            raise ValueError(f"索引必须要是pd.DatetimeIndex类型！")
    
    # 处理不同类型的输入
    if isinstance(df, (pd.Series, pd.DataFrame)):
        return _filter_single(df)
    
    elif isinstance(df, list):
        if not df:
            return []
        # 检查列表元素的类型
        if all(isinstance(item, (pd.Series, pd.DataFrame)) for item in df):
            return [_filter_single(item) for item in df]
        else:
            raise TypeError(f"列表所有元素必须是 Series 或 DataFrame")
    
    else:
        raise TypeError(f"不支持的输入类型: {type(df)}")