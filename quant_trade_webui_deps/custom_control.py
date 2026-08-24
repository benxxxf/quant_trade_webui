from .common_utils import *
from collections import deque


def folder_browser(browser_key:str):
    """
    创建文件夹选择控件，并返回用户选择的文件夹路径。

    Args:
        browser_key (str): 用于保存文件夹路径的 Streamlit 会话状态键名。

    Returns:
        str: 用户选择的文件夹路径；未选择时返回空字符串。
    """
    col1, col2 = st.columns([4, 1])
    with col1:
        current_value = st.session_state.get(browser_key, "")
        st.text_input(
        "选择文件夹",
        value=current_value,
        placeholder="请点击右侧按钮选择文件夹...",
        disabled=True,  # 只读，保留边框
        label_visibility="collapsed",
    )
    with col2:
        if st.button("📂", key=f"browse_btn_{browser_key}"):
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            st.session_state[browser_key] = filedialog.askdirectory(
                title="选择单个文件夹"
            )
            root.destroy()
            st.rerun()
    return st.session_state.get(browser_key, "")


def files_browser(browser_key:str,file_types=[("所有文件","*.*")]):
    """
    创建多文件选择控件，并返回用户选择的文件路径列表。

    Args:
        browser_key (str): 用于保存文件路径的 Streamlit 会话状态键名。
        file_types (list, optional): 文件类型过滤器列表，默认允许选择所有文件。

    Returns:
        list: 用户选择的文件路径列表；未选择时返回空列表。
    """
    col1, col2 = st.columns([4, 1])
    with col1:
        current_value = st.session_state.get(browser_key, "")
        st.text_input(
        "选择文件",
        value=current_value,
        placeholder="请点击右侧按钮选择文件...",
        disabled=True,  # 只读，保留边框
        label_visibility="collapsed",
    )


    with col2:
        if st.button("📃", key=f"browse_btn_{browser_key}"):
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            st.session_state[browser_key] = filedialog.askopenfilenames(
                title="选择多个文件",
                filetypes=file_types
            )
            root.destroy()
            st.rerun()
    return list(st.session_state.get(browser_key, ""))

class StreamlitLogger:
    """
    Streamlit 日志记录器。

    将程序输出同时转发到终端和 Streamlit 会话状态，便于在页面中展示日志。
    """

    def __init__(self):
        """
        初始化日志记录器并保存原始标准输出对象。

        Returns:
            None: 此方法只初始化对象状态，不返回数据。
        """
        # 保存原始stdout，确保终端依然有输出
        self.original_stdout = sys.__stdout__

    def write(self, text):
        """
        将文本写入终端，并按行保存到 Streamlit 会话状态。

        Args:
            text (str): 待写入的日志文本。

        Returns:
            None: 此方法只转发和保存日志，不返回数据。
        """
        # 1. 写入原始控制台 (终端)
        self.original_stdout.write(text)
        
        # 2. 捕获到 session_state
        if text and text.strip():
            # 处理多行情况
            lines = text.splitlines()
            for line in lines:
                if line.strip():
                    # 限制日志长度，避免内存无限增长
                    if len(st.session_state.logs) >= 50:
                        st.session_state.logs.pop(0)
                    st.session_state.logs.append(line)

    def flush(self):
        """
        刷新原始标准输出缓冲区。

        Returns:
            None: 此方法不返回数据。
        """
        self.original_stdout.flush()