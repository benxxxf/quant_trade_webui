from .py_loader import *
from .dataframe_plotter import *
import streamlit as st


@st.fragment
def dataviz_control_fragment():
    """
    控件函数，使用st.fragment修饰防止每次修改就对全页面重新刷新耗时过高
    只有点击加载按钮后，才会rerun然后进入到dataviz_chart_plot中绘图
    """

    # 选择单个或者多个定义好的py格式数据脚本上传，
    # 识别其中符合要求的DataFramePlotter基类并缓存
    with st.sidebar:
        st.header("📁 上传数据脚本")
        uploaded_file_list = st.file_uploader(
            "上传 .py 数据脚本",
            type=["py"],
            help="请确保脚本中定义了继承自 DataFramePlotter 的类",
            accept_multiple_files=True,
        )

        if uploaded_file_list and (not st.session_state.plotter_dict):
            for uploaded_file in uploaded_file_list:
                file_content = uploaded_file.getvalue()
                file_name = uploaded_file.name
                module = load_user_module(file_content, file_name)
                if module:
                    new_classes = extract_classes(
                        module, DataFramePlotter, construt_flag=True
                    )
                    for key, value in new_classes.items():
                        if key not in st.session_state.plotter_dict:
                            # 避免已经加载的不要重复加载,实例化的也不会清空
                            st.session_state.plotter_dict[key] = value

        # 从缓存的数据加载器中供用户选择要查看的数据对象
        # 加载后会rerun后再运行dataviz_chart_plot中，否则非外部触发一直会在片段内
        # 这样可以避免一般交互操作导致反复渲染卡顿
        if st.session_state.plotter_dict:
            selected_class_name = st.selectbox(
                "选择要加载的数据脚本", list(st.session_state.plotter_dict.keys())
            )
            st.session_state.current_plotter_class_name = selected_class_name
            selected_class = st.session_state.plotter_dict[selected_class_name]["class"]

            if selected_class.__doc__:
                st.info(f"📖 数据说明: {selected_class.__doc__}")

            if st.button("🚀 加载", type="primary", width="stretch"):
                with st.spinner("正在加载数据并生成图表..."):
                    if "obj" not in st.session_state.plotter_dict[selected_class_name]:
                        st.session_state.plotter_dict[selected_class_name][
                            "obj"
                        ] = selected_class()
                st.success("✅ 图表加载完成！")
                st.rerun()  # 跳出st.fragment并执行图表显示
            if st.button("⏹️ 清空", type="secondary", width="stretch"):
                st.session_state.plotter_dict = {}
                st.session_state.current_plotter_class_name = None
                st.rerun()
        else:
            st.info("请上传您的数据脚本(.py)")


def dataviz_chart_plot():
    """
    数据加载器具体绘图部分
    """
    # 主界面显示图表
    if st.session_state.current_plotter_class_name is not None:
        cur_obj = st.session_state.plotter_dict[
            st.session_state.current_plotter_class_name
        ]["obj"]
        st.subheader(f"📈 当前显示: {cur_obj.get_name()}")
        # 本框架是基于plotly进行绘图，如果绘图规模较复杂，本语句耗时会较高，应该尽量避免反复运行
        st.plotly_chart(
            cur_obj.get_plotly_fig(),
            theme="streamlit",
            width="stretch",
            height="stretch",  # 也可以自己设个更大的值拉长
            key="main_plotly_chart",  # 固定 key，避免重复创建
        )
    else:
        # 空状态显示
        st.info("👈 请在左侧上传数据脚本并点击「加载」按钮")


def data_viz_qtw_page():
    """
    数据可视化功能页
    """

    # 键为类名，值为字典包含"class","obj",对应类和类实例化对象
    if "plotter_dict" not in st.session_state:
        st.session_state.plotter_dict = {}
    if "current_plotter_class_name" not in st.session_state:
        st.session_state.current_plotter_class_name = None

    dataviz_control_fragment()
    dataviz_chart_plot()

    if st.session_state.current_plotter_class_name is not None:
        st.caption("🟢 图表正在显示中")
    else:
        st.caption("⏸️ 等待启动")
