import streamlit as st
import importlib.util
import sys
import os
import tempfile
import backtrader as bt


@st.cache_resource(show_spinner="正在加载用户策略...")
def load_user_module(file_content: bytes, filename: str):
    """
    将上传的py文件内容动态加载为模块

    Args:
        file_content (bytes): 字节类型的文件内容
        filename (str): 文件名

    Returns:
        _type_: 加载好的module对象
    """

    # 写入临时文件（保留原始文件名以便溯源）
    temp_dir = tempfile.gettempdir()
    safe_path = os.path.join(temp_dir, filename)

    with open(safe_path, "wb") as f:
        f.write(file_content)

    # 生成唯一模块名（避免与系统模块冲突）
    module_name = f"user_strategy_{hash(file_content) % 1000000}"

    # 如果已存在则先删除旧引用，防止重复导入
    if module_name in sys.modules:
        del sys.modules[module_name]

    # 动态导入
    spec = importlib.util.spec_from_file_location(module_name, safe_path)
    if spec is None or spec.loader is None:
        st.error("文件格式无效，无法加载")
        return None

    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
        sys.modules[module_name] = module
        return module
    except Exception as e:
        st.error(f"策略代码执行错误: {str(e)}")
        return None


def extract_classes(module, base_class, construt_flag: bool, **kwargs):
    """
    从模块中提取所有类

    Args:
        module (_type_): 模块
        base_class (_type_): 参考类
        construt_flag (bool): 是否构造标识

    Returns:
        _type_: 模块有所有类的字典
        构造标识为True的话输出{"类名":{"class":类,"obj":实例化对象},……}
        构造标识为False的话输出{"类名":{"class":类},……}
    """

    classes = {}
    for attr_name in dir(module):
        cur_class = getattr(module, attr_name)
        # 判断是否为类，且是bt.Strategy的子类，但不是基类本身
        if (
            isinstance(cur_class, type)
            and issubclass(cur_class, base_class)
            and cur_class is not base_class
        ):
            if construt_flag == True:
                classes[attr_name] = {"class": cur_class, "obj": cur_class(**kwargs)}
            else:
                classes[attr_name] = {"class": cur_class}
    return classes
