import time
import base64
import threading
import requests
import warnings
import json
import os
from bs4 import BeautifulSoup
from models import CharacterModel, ProcessState, SubTaskResult, TaskStatus,CharacterCard
from utils.doc import load_docx, load_pdf, load_text_file, load_excel
from utils.image import resize_image, blank_image,save_png
from openai import OpenAI
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# 忽略 image_reader 中 verify=False产生的警告
warnings.filterwarnings("ignore")

# 简单的内存数据库
MOCK_DB = {}

# 配置文件路径
DEBUG_MODE = True
if DEBUG_MODE:
    CONFIG_PATH = "config_test.json"
else:
    CONFIG_PATH = "config.json"

# ==========================================
# 0. 配置管理 (Config Manager)
# ==========================================

def load_config():
    """
    每次调用时重新读取配置文件，确保能够获取运行过程中的修改
    """
    if not os.path.exists(CONFIG_PATH):
        print(f"[!] Config file not found at: {CONFIG_PATH}")
        return {}
    
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[!] Error loading config: {e}")
        return {}
    
client = OpenAI(
    api_key=load_config().get("llm", {}).get("key", ""),
    base_url=load_config().get("llm", {}).get("endpoint", "")
)
# ==========================================
# 1. 核心工具函数 (Integration Helpers)
# ==========================================
def reference_info_prompts_creator(data):
    with open("backend/prompts/reference_prompts", "r", encoding="utf-8") as f:
        prompts = f.read()

    if data["reliability_score"] == 1:
        prompts = prompts.replace("%RELIABILITY%", "低")
    elif data["reliability_score"] == 2:
        prompts = prompts.replace("%RELIABILITY%", "中")
    elif data["reliability_score"] == 3:
        prompts = prompts.replace("%RELIABILITY%", "高")
    elif data["reliability_score"] == 4:
        prompts = prompts.replace("%RELIABILITY%", "确定")

    prompts = prompts.replace("%CONTENT%", data["content"])
    return prompts

def character_info_prompts_creator(data: CharacterModel):
    with open("backend/prompts/chara_info_prompts", "r", encoding="utf-8") as f:
        prompts = f.read()

    prompts = prompts.replace("%CHARACTER_NAME%", data.character_name)

    if data.character_aliases:
        CHARACTER_ALIASES = "- **角色别名:**"
        CHARACTER_ALIASES += ", ".join(data.character_aliases)
        prompts = prompts.replace("%CHARACTER_ALIASES%", CHARACTER_ALIASES)
    else:
        prompts = prompts.replace("%CHARACTER_ALIASES%", "")
    
    if data.source_work_name:
        SOURCE_WORK_NAME = "- **作品名:**"
        SOURCE_WORK_NAME += data.source_work_name
        prompts = prompts.replace("%SOURCE_WORK_NAME%", SOURCE_WORK_NAME)
    else:
        prompts = prompts.replace("%SOURCE_WORK_NAME%", "")
    
    if data.source_work_aliases:
        SOURCE_WORK_ALIASES = "- **原作别名:**"
        SOURCE_WORK_ALIASES += ", ".join(data.source_work_aliases)
        prompts = prompts.replace("%SOURCE_WORK_ALIASES%", SOURCE_WORK_ALIASES)
    else:
        prompts = prompts.replace("%SOURCE_WORK_ALIASES%", "")

    if data.user_requirement:
        prompts = prompts.replace("%USER_REQUIREMENT%", data.user_requirement)
    else:
        prompts = prompts.replace("%USER_REQUIREMENT%", "")
        
    return prompts

def search_prompts_creator(data: CharacterModel):
    with open("backend/prompts/deepresearch_prompts", "r", encoding="utf-8") as f:
        prompts = f.read()

    prompts = prompts.replace("%CHARACTER_NAME%", data.character_name)

    if data.character_aliases:
        CHARACTER_ALIASES = "- **角色别名:**"
        CHARACTER_ALIASES += ", ".join(data.character_aliases)
        prompts = prompts.replace("%CHARACTER_ALIASES%", CHARACTER_ALIASES)
    else:
        prompts = prompts.replace("%CHARACTER_ALIASES%", "")
    
    if data.source_work_name:
        SOURCE_WORK_NAME = "- **作品名:**"
        SOURCE_WORK_NAME += data.source_work_name
        prompts = prompts.replace("%SOURCE_WORK_NAME%", SOURCE_WORK_NAME)
    else:
        prompts = prompts.replace("%SOURCE_WORK_NAME%", "")
    
    if data.source_work_aliases:
        SOURCE_WORK_ALIASES = "- **原作别名:**"
        SOURCE_WORK_ALIASES += ", ".join(data.source_work_aliases)
        prompts = prompts.replace("%SOURCE_WORK_ALIASES%", SOURCE_WORK_ALIASES)
    else:
        prompts = prompts.replace("%SOURCE_WORK_ALIASES%", "")
    
    return prompts

def doc_reader(doc_path: str, config: dict = {}, type: str = "default"):
    content = ""
    if type == "default":
        try:
            if doc_path.endswith(".docx"):
                content = load_docx(doc_path)
            elif doc_path.endswith(".pdf"):
                content = load_pdf(doc_path)
            elif doc_path.endswith(".xlsx"):
                content = load_excel(doc_path)
            elif doc_path.endswith(".xls"):
                content = load_excel(doc_path)
            else:
                content = load_text_file(doc_path)
            
            return {
                "status": "success",
                "content": content,
            }
        except Exception as err:
            return {"status": "error", "message": f"An error occurred: {err}"}

def url_reader(url: str, config: dict, type: str = "jina"):
    """
    统一接口：读取URL内容
    配置来源：config['url_reader'][type]
    """
    tool_config = config.get("url_reader", {}).get(type, {})
    api_key = tool_config.get("api_key", "")

    if type == "jina":
        jina_base_url = f"https://r.jina.ai/{url}"
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; Python/3.9; JinaWrapper/1.0)"
        }
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        try:
            response = requests.get(jina_base_url, headers=headers, timeout=30)
            response.raise_for_status()
            
            return {
                "status": "success",
                "format": "markdown",
                "content": response.text,
                "url": url
            }
                
        except requests.exceptions.HTTPError as http_err:
            return {"status": "error", "message": f"HTTP error occurred: {http_err}"}
        except Exception as err:
            return {"status": "error", "message": f"An error occurred: {err}"}
    else:
        return {"status": "error", "message": f"Unknown url_reader type: {type}"}


def image_reader(image_path: str, config: dict, type: str = "deepdanbooru"):
    """
    统一接口：读取图片内容
    配置来源：config['image_reader'][type]
    """
    tool_config = config.get("image_reader", {}).get(type, {})
    
    if type == "deepdanbooru":
        cookie = tool_config.get("cookie", "")
        url = "http://dev.kanotype.net:8003/deepdanbooru/upload"

        headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
            "Accept-Language": "zh-CN,zh-HK;q=0.9,zh;q=0.8,en;q=0.7,ja;q=0.6",
            "Cache-Control": "no-cache",
            "Cookie": cookie,
            "DNT": "1",
            "Origin": "http://dev.kanotype.net:8003",
            "Pragma": "no-cache",
            "Referer": "http://dev.kanotype.net:8003/deepdanbooru/",
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
        }

        try:
            with open(image_path, "rb") as file:
                files = {"file": file}
                data = {
                    "network_type": "general",  
                    "crop": "false"  
                }

                session = requests.Session()
                response = session.post(url, files=files, data=data, headers=headers, verify=False)

            if response.status_code == 200:
                soup = BeautifulSoup(response.text, "html.parser")
                td_elements = soup.find_all('td')
                tags = [td.find('a').text for td in td_elements if td.find('a')]
                filtered_tags = [tag for tag in tags if 'rating' not in tag]
                
                result_string = ",".join(filtered_tags)
                return {"status": "success", "content": result_string}
            else:
                raise ValueError(f"Fetch error: Status code {response.status_code}")
                
        except Exception as e:
            return {"status": "error", "message": str(e)}
    else:
        return {"status": "error", "message": f"Unknown image_reader type: {type}"}


def search_reader(query: str, config: dict, type: str = "google"):
    """
    统一接口：执行搜索
    配置来源：config['search_engine'][type_key]
    注意：代码逻辑中的 type 可能与 config key 不完全一致，这里做映射处理
    """
    
    # 映射逻辑类型到配置键
    config_key = "google" if "google" in type else type
    if type == "google-deepresearch":
        config_key = "google"
    elif type == "tavily":
        config_key = "tavily"
        
    tool_config = config.get("search_engine", {}).get(config_key, {})
    api_key = tool_config.get("api_key", "")
    
    if not api_key:
         return {"status": "error", "message": f"Missing API Key for search type: {config_key}"}
    if type == "google-deepresearch" or type == "google":
        try:
            print(f"[*] Starting Deep Research for: \n{query[:150]}...")
            if DEBUG_MODE:
                with open("debug/search_reader_prompts", "w", encoding="utf-8") as f:
                    f.write(query)
            
            # === 1. 构建请求 ===
            base_url = "https://generativelanguage.googleapis.com/v1beta/interactions"
            headers = {
                "Content-Type": "application/json",
                "x-goog-api-key": api_key
            }
            payload = {
                "input": query,
                "agent": "deep-research-pro-preview-12-2025",
                "background": True
            }
            # 【增加】请求层的重试策略，防止第一次握手就失败
            session = requests.Session()
            retries = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
            session.mount('https://', HTTPAdapter(max_retries=retries))
            try:
                # 使用 session 发送请求
                response = session.post(base_url, headers=headers, json=payload, timeout=60)
            except requests.exceptions.RequestException as req_err:
                 return {"status": "error", "message": f"Network Error (Initial Request): {req_err}"}
            if response.status_code != 200:
                print(f"[DEBUG] Error Body: {response.text}")
                return {"status": "error", "message": f"API Error ({response.status_code})"}
            
            data = response.json()
            
            # === 2. 获取 Interaction ID ===
            interaction_id = None
            if "id" in data:
                interaction_id = data["id"]
            elif "name" in data:
                interaction_id = data["name"].split("/")[-1]
            
            if not interaction_id:
                print(f"[DEBUG] Response: {data}")
                return {"status": "error", "message": "Cannot find 'id' in response."}
            
            print(f"[*] Research ID: {interaction_id}. Waiting for completion...")
            # === 3. 轮询状态 (修改核心部分) ===
            poll_url = f"{base_url}/{interaction_id}"
            max_retries = tool_config.get("timeout", 30) * 6
            count = 0
            
            # 连续网络错误计数器（防止死循环）
            consecutive_net_errors = 0 
            MAX_CONSECUTIVE_ERRORS = 10 
            while count < max_retries:
                time.sleep(10) 
                count += 1
                
                try:
                    # 【核心修改】将 GET 请求包裹在 try-except 中
                    # 这里也可以复用上面的 session，但为了保险起见，这里独立捕获更灵活
                    check_resp = requests.get(poll_url, headers=headers, timeout=30)
                    
                    # 如果请求成功，重置连续错误计数
                    consecutive_net_errors = 0 
                except requests.exceptions.RequestException as e:
                    # 【关键点】捕获网络异常（SSL, Timeout, ConnectionError等）
                    consecutive_net_errors += 1
                    err_msg = str(e)
                    # 只有连续错误多次才打印详细日志，避免刷屏，或者简单的提示
                    print(f"[!] Network fluctuation ({consecutive_net_errors}/{MAX_CONSECUTIVE_ERRORS}): {err_msg.split('(')[0]}... Retrying...")
                    
                    if consecutive_net_errors >= MAX_CONSECUTIVE_ERRORS:
                        return {"status": "error", "message": f"Polling failed: Network unstable ({str(e)})"}
                    
                    # 遇到网络错误，直接跳过本次循环，进入下一次 sleep 和重试
                    continue
                # --- 以下是正常的 HTTP 状态码处理 ---
                if check_resp.status_code != 200:
                    print(f"[!] Polling HTTP error ({check_resp.status_code}). Retrying...")
                    # HTTP 错误也视为一种需要重试的情况，不立即报错
                    continue
                
                try:
                    check_data = check_resp.json()
                except ValueError:
                    print("[!] Invalid JSON received. Retrying...")
                    continue
                status = check_data.get("status")
                print(f"[DEBUG] Response: {check_data}")
                print(f"[*] Research Status ({count*10}s): {status}") 
                
                if status == "completed":
                    outputs = check_data.get("outputs", [])
                    if outputs:
                        content = outputs[-1].get("text", "")
                        return {"status": "success", "content": content}
                    else:
                        return {"status": "error", "message": "Deep Research completed but output is empty."}
                
                elif status == "failed":
                    error_msg = check_data.get("error", "Unknown error")
                    return {"status": "error", "message": f"Deep Research Failed: {error_msg}"}
            
            return {"status": "error", "message": "Timeout: Research took too long."}
        except Exception as e:
            return {"status": "error", "message": f"Exception: {str(e)}"}
    
    elif type == "tavily":
        # 预留给 Tavily 的实现
        return {"status": "error", "message": "Tavily implementation not included in this snippet"}
        
    else:
        return {"status": "error", "message": "Unknown search type"}


# ==========================================
# 2. 业务逻辑层 (Service Layer)
# ==========================================

def get_task_status(process_id: str) -> ProcessState:
    return MOCK_DB.get(process_id)

def start_processing_background(character_data: CharacterModel, process_id: str):
    initial_state = ProcessState(
        process_id=process_id, 
        sub_tasks=[],
        character_info=character_data 
    )
    MOCK_DB[process_id] = initial_state
    
    t = threading.Thread(
        target=_processing_logic, 
        args=(process_id, character_data)
    )
    t.start()

def _processing_logic(process_id: str, data: CharacterModel):
    """
    真实处理逻辑
    """
    # === 1. 获取最新配置 ===
    # 在任务开始执行时读取配置，确保动态修改生效
    current_config = load_config()
    
    current_state = MOCK_DB[process_id]
    
    # --- 2. 规划任务队列 ---
    tasks_queue = []

    # 遍历用户上传的资料
    for idx, ref in enumerate(data.reference):
        print(f"[*] Processing Reference: {ref}")
        print(f"[*] Cureliability_score: {ref.reliability_score}")
        title = ""
        t_type = ""
        
        task_payload = {"ref_obj": ref}

        if ref.resource_type == "image":
            title = f"视觉分析: {ref.file_name or 'Image'}"
            t_type = "image_analysis"
        elif ref.resource_type == "file":
            title = f"文档处理: {ref.file_name or 'Document'}"
            t_type = "doc_analysis"
        elif ref.resource_type == "url":
            title = f"链接读取: {ref.resource_url}"
            t_type = "link_crawl"
        elif ref.resource_type == "search":
            title = f"网络搜索: {data.character_name}"
            t_type = "search"
            task_payload["ref_obj"].resource_url = search_prompts_creator(data)
        
        tasks_queue.append({
            "step_id": f"step_ref_{idx}",
            "title": title,
            "type": t_type,
            "payload": task_payload
        })
    
    
    for task_def in tasks_queue:
        # 创建并展示任务（状态：处理中）
        sub_task = SubTaskResult(
            step_id=task_def["step_id"],
            title=task_def["title"],
            type=task_def["type"],
            status=TaskStatus.PROCESSING,
            reliability_score=task_def["payload"]["ref_obj"].reliability_score
        )
        current_state.sub_tasks.append(sub_task)
        
        # 获取刚才添加的任务引用，以便更新
        current_sub_task = next(t for t in current_state.sub_tasks if t.step_id == task_def["step_id"])
        
        try:
            result_content = ""
            
            # === 分支处理逻辑 ===
            if task_def["type"] == "image_analysis":
                image_path = task_def["payload"]["ref_obj"].resource_url
                print(f"[*] Processing Image: {image_path}")
                
                res = image_reader(
                    image_path=image_path, 
                    config=current_config,
                    type="deepdanbooru"
                )
                
                if res["status"] == "success":
                    result_content = res["content"]
                else:
                    raise Exception(res["message"])

            elif task_def["type"] == "link_crawl":
                target_url = task_def["payload"]["ref_obj"].resource_url
                print(f"[*] Crawling URL: {target_url}")
                
                # Dynamic Config Injection: 使用 current_config
                res = url_reader(
                    url=target_url, 
                    config=current_config,
                    type="jina"
                )
                
                if res["status"] == "success":
                    result_content = res["content"]
                else:
                    raise Exception(res["message"])
            
            elif task_def["type"] == "doc_analysis":
                doc_path = task_def["payload"]["ref_obj"].resource_url
                res = doc_reader(
                    doc_path=doc_path,
                )
                if res["status"] == "success":
                    result_content = res["content"]
                else:
                    raise Exception(res["message"])
                
            elif task_def["type"] == "search":

                res = search_reader(
                    query=task_def["payload"]["ref_obj"].resource_url, 
                    config=current_config,
                    type="google-deepresearch"
                )
                
                if res["status"] == "success":
                    result_content = res["content"]
                else:
                    raise Exception(res["message"])

            # === 任务成功 ===
            current_sub_task.status = TaskStatus.SUCCESS
            current_sub_task.result_summary = result_content
            
        except Exception as e:
            # === 任务失败 ===
            print(f"[!] Task failed: {e}")
            current_sub_task.status = TaskStatus.FAILED
            current_sub_task.result_summary = f"Error: {str(e)}"
    
    # 全部流程结束
    current_state.is_finished = True
    print(f"Process {process_id} finished completely.")

# ==========================================
# 3. 新增：交互与生成逻辑
# ==========================================

def update_subtask_result(process_id: str, step_id: str, new_summary: str):
    """
    前端用户在 UI 上修改了某个步骤的解析结果，调用此函数更新内存状态
    """
    state = MOCK_DB.get(process_id)
    if not state:
        raise ValueError("Process ID not found")
    
    for task in state.sub_tasks:
        if task.step_id == step_id:
            task.result_summary = new_summary
            print(f"[*] Updated Task {step_id} with new content (len={len(new_summary)})")
            return True
    return False

def start_card_generation(process_id: str):
    """
    触发最终生成任务：
    1. 收集所有已完成的 sub_tasks (包含用户修改后的 result_summary 和 reliability_score)
    2. 结合 CharacterModel
    3. 调用 LLM 生成 JSON
    """
    state = MOCK_DB.get(process_id)
    if not state:
        raise ValueError("Process ID not found")

    # 添加一个“生成中”的任务状态，让前端感知到进入了 Step 4 处理
    gen_task_id = "step_final_gen"
    gen_task = SubTaskResult(
        step_id=gen_task_id,
        title="正在根据资料构建人物卡...",
        type="card_generation",
        status=TaskStatus.PROCESSING,
        reliability_score=5 # 最高权重
    )
    state.sub_tasks.append(gen_task)
    state.is_finished = False # 重置完成状态，因为加了新任务

    # 启动后台生成线程
    t = threading.Thread(target=_generation_logic, args=(process_id,))
    t.start()

def _generation_logic(process_id: str):
    state = MOCK_DB[process_id]
    character_data = state.character_info
    
    # 1. 聚合数据
    # 这里将所有之前的分析结果打包
    analyzed_materials = []
    for task in state.sub_tasks:
        if task.type == "card_generation": continue # 跳过自己
        if task.status == TaskStatus.SUCCESS and task.result_summary:
            analyzed_materials.append({
                "source_type": task.type,
                "content": task.result_summary,
                "reliability_score": task.reliability_score
            })
    
    print(f"[*] Starting LLM Generation for {character_data.character_name} with {len(analyzed_materials)} materials.")

    try:
        # 2. 调用生成函数 (这里是你需要实现的地方)
        # 你可以在这里构建 Prompt，传入 character_data 和 analyzed_materials
        final_json_str = _mock_llm_generation(character_data, analyzed_materials)
        
        # 3. 更新状态
        state.final_json = final_json_str
        
        # 更新任务状态
        target_task = next(t for t in state.sub_tasks if t.step_id == "step_final_gen")
        target_task.status = TaskStatus.SUCCESS
        target_task.result_summary = "人物卡生成完毕"
        
        # 标记整个流程彻底结束
        state.is_finished = True
        
    except Exception as e:
        print(f"[!] Generation Failed: {e}")
        target_task = next(t for t in state.sub_tasks if t.step_id == "step_final_gen")
        target_task.status = TaskStatus.FAILED
        target_task.result_summary = f"生成失败: {str(e)}"
        state.is_finished = True

def _mock_llm_generation(char_data: CharacterModel, materials: list) -> str:
    with open("backend/prompts/card_genrate_prompts", "r", encoding="utf-8") as f:
        sys_prompts = f.read()

    have_image = False
    image_path = ""

    messages = []
    messages.append({"role": "system", "content": sys_prompts})
    messages.append({"role": "user", "content": character_info_prompts_creator(char_data)})

    if DEBUG_MODE:
        with open("debug/llm_generation_prompts", "w", encoding="utf-8") as f:
            f.write(sys_prompts + character_info_prompts_creator(char_data))
        
    for material in materials:
        messages.append({"role": "user", "content": reference_info_prompts_creator(material)})

    for r in char_data.reference:
        if r.resource_type == "image":
            have_image = True
            image_path = r.resource_url
            break
        

    response = client.chat.completions.create(
        model=load_config().get("llm", {}).get("model", ""),
        messages=messages
    )

    raw_text = response.choices[0].message.content
    def extract_json(text: str) -> dict:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1:
            raise ValueError("No JSON object found")
        return json.loads(text[start:end + 1])
    

    card_dict = extract_json(raw_text)
    json_str = json.dumps(card_dict, ensure_ascii=False, indent=4)

    if have_image:
        image = resize_image(image_path)
    else:
        image = blank_image()

    output_image = save_png(image, json_str)

    output_image = base64.b64encode(output_image).decode("utf-8")

    return json.dumps({"json": json_str,"image": output_image}, ensure_ascii=False, indent=4)