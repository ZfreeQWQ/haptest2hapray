import os
import json

# ==== ✅ 配置区域：你可以修改这些信息 ====
CLASS_NAME = "ResourceUsage_PerformanceDynamic_xiangce_0010"
APP_PACKAGE = "com.huawei.hmos.photos"
APP_NAME = "图库"
JSON_FOLDER = "E:\\hapProjects\\haptest\\out\\2025-04-21-16-00-16\\events"
OUTPUT_FILE = f"{CLASS_NAME}.py"
# =========================================

def extract_event_info(json_data):
    """
    从单个 json 中提取 event 操作信息，返回 (action_code, 描述)
    支持 TouchEvent、LongTouchEvent、DoubleClickEvent、ScrollEvent、
          InputTextEvent、SwipeEvent、FlingEvent、DragEvent
    """
    event = json_data.get("event", {})
    ev_type = event.get("type", "")
    component = event.get("component", {}) or {}
    point = event.get("point")
    text = component.get("text", "").strip()
    bounds = component.get("origBounds", [])
    input_text = event.get("text", "")  # InputTextEvent 专用

    # 辅助：计算 bounds 中心点
    def center_of(bounds):
        (x1, y1), (x2, y2) = (bounds[0]['x'], bounds[0]['y']), (bounds[1]['x'], bounds[1]['y'])
        return ( (x1+x2)//2, (y1+y2)//2 )

    # 生成定位表达式，优先 text → point → bounds center
    def gen_locator():
        if text:
            return f"BY.type('Text').text({json.dumps(text)})", f"点击文本『{text}』"
        if point:
            x, y = point['x'], point['y']
            return (x, y), f"点击坐标({x},{y})"
        if bounds:
            cx, cy = center_of(bounds)
            return (cx, cy), f"点击区域中心({cx},{cy})"
        return None, "未知操作"

    locator, desc = gen_locator()

    # 根据事件类型，生成实际的 driver 调用
    if ev_type == "TouchEvent":
        if isinstance(locator, str):
            action = f"driver.touch({locator})"
        else:
            action = f"driver.touch(({locator[0]}, {locator[1]}))"
    elif ev_type == "LongTouchEvent":
        if isinstance(locator, str):
            action = f"driver.long_touch({locator})"
        else:
            action = f"driver.long_touch({locator[0]}, {locator[1]}, duration=2000)"
            # duration 可自定义，这里示例为 2000ms
        desc = desc.replace("点击", "长按")
    elif ev_type == "DoubleClickEvent":
        if isinstance(locator, str):
            action = f"driver.double_click({locator})"
        else:
            action = f"driver.double_click(({locator[0]}, {locator[1]}))"
        desc = desc.replace("点击", "双击")
    elif ev_type == "ScrollEvent":
        # ScrollEvent 可能含有 direction/percent
        dir_ = event.get("direction", "down")
        pct = event.get("percent", 0.5)
        action = f"driver.scroll(direction={json.dumps(dir_)}, percent={pct})"
        desc = f"滚动方向 {dir_}，比例 {pct}"
    elif ev_type == "SwipeEvent":
        # SwipeEvent 可能含有 start/end 点或 direction
        if 'start' in event and 'end' in event:
            sx, sy = event['start']['x'], event['start']['y']
            ex, ey = event['end']['x'], event['end']['y']
            action = f"driver.swipe(start_x={sx}, start_y={sy}, end_x={ex}, end_y={ey}, duration=500)"
            desc = f"滑动从({sx},{sy})到({ex},{ey})"
        else:
            dir_ = event.get("direction", "up")
            action = f"driver.swipe(direction={json.dumps(dir_)}, percent=0.5)"
            desc = f"滑动方向 {dir_}"
    elif ev_type == "FlingEvent":
        dir_ = event.get("direction", "up")
        speed = event.get("speed", 1000)
        action = f"driver.fling(direction={json.dumps(dir_)}, speed={speed})"
        desc = f"快速滑动方向 {dir_}，速度 {speed}"
    elif ev_type == "DragEvent":
        # DragEvent 通常有 from/to
        frm = event.get("from")
        to = event.get("to")
        if frm and to:
            fx, fy = frm['x'], frm['y']
            tx, ty = to['x'], to['y']
            action = f"driver.drag(start_x={fx}, start_y={fy}, end_x={tx}, end_y={ty}, duration=800)"
            desc = f"拖拽从({fx},{fy})到({tx},{ty})"
        else:
            action = "# DragEvent 但无 from/to 信息"
    elif ev_type == "InputTextEvent":
        txt = input_text or component.get("text", "")
        txt_literal = json.dumps(txt)  # 自动加引号 + 转义
        if locator:
            if isinstance(locator, str):
                action = f"driver.input_text({locator}, {txt_literal})"
            else:
                action = f"driver.input_text(({locator[0]}, {locator[1]}), {txt_literal})"
        else:
            action = f"driver.input_text(None, {txt_literal})"
        desc = f"输入文本 {txt_literal}"
    else:
        action = "# 未支持的事件类型：" + ev_type
        desc = f"未知事件 {ev_type}"

    return action, desc


def generate_test_code(json_dir, class_name, app_package, app_name):
    steps_code = []
    step_defs = []
    step_descs = []

    file_list = sorted(f for f in os.listdir(json_dir) if f.endswith(".json"))

    for idx, file_name in enumerate(file_list, start=1):
        with open(os.path.join(json_dir, file_name), 'r', encoding='utf-8') as f:
            data = json.load(f)

        action_code, desc = extract_event_info(data)
        step_name = f"step{idx}"
        step_descs.append({
            "name": step_name,
            "description": f"{idx}. {desc}"
        })
        step_defs.append(f"""
        def {step_name}(driver):
            Step('{idx}. {desc}')
            {action_code}
            time.sleep(2)
        """)
        steps_code.append(f"        self.execute_step_with_perf({idx}, {step_name}, 10)")

    final_code = f'''# coding: utf-8
import os
import time

from devicetest.core.test_case import Step
from hypium import BY
from aw.PerfTestCase import PerfTestCase, Log

class {class_name}(PerfTestCase):

    def __init__(self, controllers):
        self.TAG = self.__class__.__name__
        super().__init__(self.TAG, controllers)

        self._app_package = '{app_package}'
        self._app_name = '{app_name}'
        self._steps = {json.dumps(step_descs, indent=8, ensure_ascii=False)}

    @property
    def steps(self):
        return self._steps

    @property
    def app_package(self):
        return self._app_package

    @property
    def app_name(self):
        return self._app_name

    def setup(self):
        Log.info('setup')
        os.makedirs(os.path.join(self.report_path, 'hiperf'), exist_ok=True)
        os.makedirs(os.path.join(self.report_path, 'report'), exist_ok=True)

    def process(self):
        self.driver.swipe_to_home()
        self.driver.start_app(self.app_package)
        self.driver.wait(3)
{"".join(step_defs)}
{os.linesep.join(steps_code)}

    def teardown(self):
        Log.info('teardown')
        self.driver.stop_app(self.app_package)
        self.make_reports()
'''
    return final_code

# === 运行并输出 ===
if __name__ == '__main__':
    code = generate_test_code(JSON_FOLDER, CLASS_NAME, APP_PACKAGE, APP_NAME)
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(code)
    print(f'✅ 生成完毕: {OUTPUT_FILE}')
