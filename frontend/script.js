// 全局状态
let currentStep = 1;
const totalSteps = 4;
let processId = null; // 存储后端返回的任务ID
let pollingInterval = null; // 轮询句柄
let processedStepIds = new Set(); // 记录已经渲染过的子任务ID

const RELIABILITY_MAP = { "低": 1, "中": 2, "高": 3, "确信": 4 };
const RESOURCE_TYPE_MAP = { "链接": "url", "文档": "file", "图片": "image", "搜索": "search" };

const FILE_LIMITS = {
    '图片': {
        accept: '.jpg,.jpeg,.png,.webp,.gif',
        exts: ['jpg', 'jpeg', 'png', 'webp', 'gif'],
        msg: '请上传 JPG, PNG, WEBP 或 GIF 图片'
    },
    '文档': {
        accept: '.txt,.pdf,.md,.xls,.xlsx,.docx',
        exts: ['txt', 'pdf', 'md', 'xls', 'xlsx', 'docx'],
        msg: '请上传 TXT, PDF, MD , EXCEL或 Word 文档'
    }
};

document.addEventListener("DOMContentLoaded", () => {
    // 初始化一些资料框
    if (document.getElementById('reference-list').children.length === 0) {
        addReferenceItem();
    }
    document.getElementById('add-ref-btn').addEventListener('click', addReferenceItem);
    updateButtons();

    // 初始化Step 1假数据方便测试 (可选)
    document.getElementById('character_name').value = "";
});

// === 导航逻辑 ===
function changeStep(n) {
    // 校验 Step 1
    if (n === 1 && currentStep === 1 && !validateStep(currentStep)) return;

    // Logic for Step 2 -> 3 (Submit)
    if (currentStep === 2 && n === 1) {
        startProcessingFlow();
        return;
    }

    // Logic for Step 3 -> 4 (Generate)
    if (currentStep === 3 && n === 1) {
        triggerGeneration();
        return;
    }

    proceedStepChange(n);
}

async function triggerGeneration() {
    if (!processId) return;

    // 界面进入 Step 4
    proceedStepChange(1);

    // Step 4 UI 初始化状态
    const step4Div = document.getElementById('step-4');
    step4Div.innerHTML = `
        <div class="processing-header">
            <h3><i class="fa-solid fa-wand-magic-sparkles fa-spin"></i> 正在生成人物卡...</h3>
            <p class="sub-text">整合所有分析数据，正在请求 LLM 构建 JSON。</p>
        </div>
    `;

    try {
        // 调用后端触发生成
        await fetch('/api/file/generate_card', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ process_id: processId })
        });

        if (pollingInterval) clearInterval(pollingInterval);
        pollingInterval = setInterval(pollStatus, 1000);
        console.log("Generation polling started.");

    } catch (e) {
        alert("生成请求发送失败");
    }
}
function proceedStepChange(n) {
    document.getElementById(`step-${currentStep}`).classList.remove('active');
    document.getElementById(`indicator-${currentStep}`).classList.remove('active');

    currentStep += n;
    if (currentStep > totalSteps) currentStep = totalSteps;
    if (currentStep < 1) currentStep = 1;

    document.getElementById(`step-${currentStep}`).classList.add('active');
    document.getElementById(`indicator-${currentStep}`).classList.add('active');

    updateButtons();
}

function updateButtons() {
    const prevBtn = document.getElementById("prevBtn");
    const nextBtn = document.getElementById("nextBtn");
    // 上一步逻辑
    if (currentStep === 1 || currentStep === 3 || currentStep === 4) {
        prevBtn.classList.add("hidden");
    } else {
        prevBtn.classList.remove("hidden");
    }
    // 下一步逻辑
    if (currentStep === totalSteps) {
        nextBtn.classList.add("hidden");
    } else if (currentStep === 3) {
        nextBtn.classList.add("hidden");
    } else {
        nextBtn.classList.remove("hidden");
        nextBtn.textContent = (currentStep === totalSteps - 1) ? "导出结果" : "下一步";
    }
}

function validateStep(step) {
    if (step === 1) {
        if (!document.getElementById('character_name').value) return false;
    }
    return true;
}

async function startProcessingFlow() {
    proceedStepChange(1);

    // 重置状态
    document.getElementById('task-list-container').innerHTML = '';
    processedStepIds.clear();
    document.getElementById('processing-done-msg').classList.add('hidden');

    const formData = packFormData();
    try {
        // 这里假设后端 API 路径
        const response = await fetch('/api/file/submit', {
            method: 'POST',
            body: formData
        });

        // --- 模拟测试逻辑 Start (如果没有实际后端，可保留此段用于 UI 测试) ---
        // 实际使用时请删除此处 Mock 逻辑，改为下面的真实逻辑
        /*
        setTimeout(() => {
             renderTasks([{step_id: '101', title: '读取 Wiki 资料', status: 'processing'}]);
             setTimeout(() => {
                 renderTasks([{step_id: '101', title: '读取 Wiki 资料', status: 'success', result_summary:'角色名为フラウ，别名Frau。'}]);
                 renderTasks([{step_id: '102', title: '分析设定图', status: 'processing'}]);
             }, 2000);
             setTimeout(() => {
                 renderTasks([{step_id: '102', title: '分析设定图', status: 'success', result_summary:'发色：银色，瞳色：红色，服装：女仆装。'}]);
                 finishProcessing();
             }, 4000);
        }, 500);
        return; 
        */
        // --- 模拟测试逻辑 End ---

        if (response.ok) {
            const result = await response.json();
            processId = result.process_id;
            console.log("Task started:", processId);
            pollingInterval = setInterval(pollStatus, 1000);
        } else {
            alert("提交失败，请检查控制台");
            changeStep(-1);
        }
    } catch (e) {
        console.error(e);
        alert("网络错误或API未连接");
        changeStep(-1);
    }
}

function packFormData() {
    const charName = document.getElementById('character_name').value;
    const charAliasesStr = document.getElementById('character_aliases').value;
    const charAliases = charAliasesStr ? charAliasesStr.split(/[,，]/).map(s => s.trim()).filter(s => s) : [];
    const workName = document.getElementById('source_work_name').value;

    const workAliasesStr = document.getElementById('source_work_aliases').value;
    const workAliases = workAliasesStr ? workAliasesStr.split(/[,，]/).map(s => s.trim()).filter(s => s) : [];
    const requirement = document.getElementById('user_requirement').value;

    const references = [];
    const filesToUpload = [];
    document.querySelectorAll('.reference-card').forEach(item => {
        const typeSelect = item.querySelectorAll('select')[0];
        const scoreSelect = item.querySelectorAll('select')[1];
        const typeVal = RESOURCE_TYPE_MAP[typeSelect.value];
        const scoreVal = RELIABILITY_MAP[scoreSelect.value];

        let urlVal = "";
        let fName = null;

        if (typeVal === 'url') {
            urlVal = item.querySelector('.ref-url-input').value;
        } else {
            const fileInput = item.querySelector('.ref-file-input');
            if (fileInput.files.length > 0) {
                filesToUpload.push(fileInput.files[0]);
                urlVal = "PENDING_UPLOAD";
                fName = fileInput.files[0].name;
            }
        }
        references.push({
            resource_type: typeVal,
            reliability_score: scoreVal,
            resource_url: urlVal,
            file_name: fName
        });
    });
    const dataObj = {
        character_name: charName,
        character_aliases: charAliases,
        source_work_name: workName,
        source_work_aliases: workAliases,
        user_requirement: requirement,
        reference: references
    };
    const formData = new FormData();
    formData.append('data', JSON.stringify(dataObj));
    filesToUpload.forEach(f => formData.append('files', f));
    return formData;
}

// 轮询函数
async function pollStatus() {
    if (!processId) return;
    try {
        const res = await fetch(`/api/file/status/${processId}`);
        if (!res.ok) return;

        const state = await res.json();

        // === 逻辑 A: Step 3 (解析阶段) ===
        if (currentStep === 3) {
            renderTasks(state.sub_tasks);
            if (state.is_finished) {
                finishProcessing();
                // 停止轮询，并显式设为 null
                clearInterval(pollingInterval);
                pollingInterval = null;
            }
        }

        // === 逻辑 B: Step 4 (生成阶段) ===
        if (currentStep === 4) {
            // 优先检查是否有结果
            if (state.final_json) {
                renderFinalResult(JSON.parse(state.final_json));
                clearInterval(pollingInterval);
                pollingInterval = null;
            }
            // 兜底：如果后端说 finished 了但没 json，可能是出错了
            else if (state.is_finished) {
                // 检查是否有失败的任务
                const failedTask = state.sub_tasks.find(t => t.type === 'card_generation' && t.status === 'failed');
                if (failedTask) {
                    document.getElementById('step-4').innerHTML = `
                        <div class="error-card">
                            <i class="fa-solid fa-triangle-exclamation"></i>
                            <h3>生成失败</h3>
                            <p>${failedTask.result_summary || "未知错误"}</p>
                        </div>`;
                }
                clearInterval(pollingInterval);
                pollingInterval = null;
            }
        }

    } catch (e) {
        console.error("Polling error", e);
    }
}
function renderFinalResult(jsonStr) {
    // 将最终的 JSON 字符串保存在全局变量中，供下载函数使用
    window.finalJsonData = jsonStr;

    const step4Div = document.getElementById('step-4');
    step4Div.innerHTML = `
        <div class="success-card fade-in">
          <div class="success-icon"><i class="fa-solid fa-file-export"></i></div>
          <h3>人物卡生成完毕</h3>
          <p>您的SillyTavern人物卡已准备就绪。</p>
          <div class="action-buttons" style="justify-content: center; display: flex; gap: 15px; margin-top: 25px;">
            <button type="button" class="btn btn-primary" onclick="downloadCard('png')">
                <i class="fa-solid fa-image"></i> 下载 PNG 卡片
            </button>
            <button type="button" class="btn btn-outline" onclick="downloadCard('json')">
                <i class="fa-solid fa-file-code"></i> 下载 JSON 文件
            </button>
          </div>
          
        </div>
    `;
}
//在此处实现下载逻辑
window.downloadCard = function (type) {
    if (!window.finalJsonData) {
        alert("数据尚未准备好，请稍后再试。");
        return;
    }

    if (type === 'json') {
        // 下载 JSON 文件
        try {
            const blob = new Blob([window.finalJsonData.json], { type: "application/json" });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;

            // 尝试从 JSON 中获取角色名作为文件名
            let fileName = "character_card.json";
            try {
                const jsonObj = JSON.parse(window.finalJsonData.json);
                if (jsonObj.name) {
                    // 简单过滤文件名中的非法字符
                    fileName = jsonObj.name.replace(/[^a-z0-9_\-\.\u4e00-\u9fa5]/gi, '_') + ".json";
                }
            } catch (e) { /* json 解析失败则使用默认文件名 */ }

            a.download = fileName;
            document.body.appendChild(a); // FireFox 需要添加到 DOM 才能点击
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        } catch (e) {
            console.error("Download failed:", e);
            alert("下载 JSON 失败");
        }

    } else if (type === 'png') {
        try {
            if (!window.finalJsonData.image) {
                alert("未找到图片数据");
                return;
            }

            // Base64 转 Blob
            const base64 = window.finalJsonData.image;
            const binary = atob(base64);
            const len = binary.length;
            const bytes = new Uint8Array(len);

            for (let i = 0; i < len; i++) {
                bytes[i] = binary.charCodeAt(i);
            }

            const blob = new Blob([bytes], { type: "image/png" });
            const url = URL.createObjectURL(blob);

            // 生成文件名（优先用角色名）
            let fileName = "character_card.png";
            try {
                const jsonObj = JSON.parse(window.finalJsonData.json);
                if (jsonObj.name) {
                    fileName =
                        jsonObj.name.replace(/[^a-z0-9_\-\.\u4e00-\u9fa5]/gi, "_")
                        + ".png";
                }
            } catch (e) { }

            const a = document.createElement("a");
            a.href = url;
            a.download = fileName;
            document.body.appendChild(a);
            a.click();

            document.body.removeChild(a);
            URL.revokeObjectURL(url);

        } catch (e) {
            console.error("PNG 下载失败:", e);
            alert("下载 PNG 失败");
        }
    }
}


// function escapeHtml(text) {
//   return text
//       .replace(/&/g, "&amp;")
//       .replace(/</g, "&lt;")
//       .replace(/>/g, "&gt;")
//       .replace(/"/g, "&quot;")
//       .replace(/'/g, "&#039;");
// }

// 渲染列表
function renderTasks(subTasks) {
    const container = document.getElementById('task-list-container');

    subTasks.forEach(task => {
        let itemEl = document.getElementById(`task-${task.step_id}`);

        if (!itemEl) {
            itemEl = createTaskElement(task);
            container.appendChild(itemEl);
            processedStepIds.add(task.step_id);
            itemEl.scrollIntoView({ behavior: 'smooth', block: 'end' });
        } else {
            updateTaskElement(itemEl, task);
        }
    });
}

function createTaskElement(task) {
    const div = document.createElement('div');
    div.id = `task-${task.step_id}`;
    // 改为列布局，以便垂直排列 Header 和 EditBox
    div.className = `task-item ${task.status}`;

    div.innerHTML = `
        <!-- 上部分：标题、状态、图标 -->
        <div class="task-header">
            <div class="task-info">
                <span class="task-title">${task.title}</span>
                <span class="task-status-text">${getStatusText(task.status)}</span>
                <!-- 占位：成功后显示按钮 -->
                <div class="task-actions-wrapper"></div>
            </div>
            <div class="task-icon-wrapper">
                ${getStatusIconHtml(task.status)}
            </div>
        </div>
        
        <!-- 下部分：折叠的编辑区 (宽度与 task-item 一致) -->
        <div class="task-edit-area" id="edit-area-${task.step_id}" style="display:none;">
            <div class="edit-area-inner">
                <textarea id="input-${task.step_id}" class="task-textarea" placeholder="解析结果将显示在这里..."></textarea>
                <div class="edit-toolbar">
                    <button type="button" class="btn-mini btn-save" onclick="saveTaskResult('${task.step_id}')">
                        <i class="fa-solid fa-check"></i> 确认/保存
                    </button>
                    <span class="edit-tip"><i class="fa-solid fa-pen"></i> 请在此校对解析结果</span>
                </div>
            </div>
        </div>
    `;

    // 如果初始创建时已经是完成状态，注入结果
    if (task.status === 'success' && task.result_summary) {
        // 使用 setTimeout 确保 DOM 插入后再执行
        setTimeout(() => injectSuccessState(div, task), 0);
    }

    return div;
}

function updateTaskElement(el, task) {
    // 1. 更新顶部状态 class
    if (!el.classList.contains(task.status)) {
        el.classList.remove('pending', 'processing', 'success', 'failed');
        el.classList.add(task.status);

        // 更新文字
        el.querySelector('.task-status-text').textContent = getStatusText(task.status);
        // 更新图标
        el.querySelector('.task-icon-wrapper').innerHTML = getStatusIconHtml(task.status);

        // 如果变成了 success，注入编辑功能
        if (task.status === 'success') {
            injectSuccessState(el, task);
        }
    }
}

// 辅助：注入成功状态的数据和按钮
function injectSuccessState(el, task) {
    const stepId = task.step_id;
    const resultText = task.result_summary || "";

    // 1. 在 task-actions-wrapper 插入“查看/编辑”按钮
    const actionWrapper = el.querySelector('.task-actions-wrapper');
    if (actionWrapper && actionWrapper.innerHTML === '') {
        actionWrapper.innerHTML = `
            <button type="button" class="btn-preview" onclick="toggleTaskEdit('${stepId}')">
                <i class="fa-solid fa-pen-to-square"></i> 查看与编辑解析结果
            </button>
        `;
    }

    // 2. 填充 Textarea
    const textarea = el.querySelector(`#input-${stepId}`);
    if (textarea && !textarea.value) {
        textarea.value = resultText;
    }
}

// 切换编辑框显示/隐藏
window.toggleTaskEdit = function (stepId) {
    const area = document.getElementById(`edit-area-${stepId}`);
    const btn = document.querySelector(`#task-${stepId} .btn-preview`);

    if (area.style.display === 'none') {
        // 展开动画
        area.style.display = 'block';
        if (btn) btn.classList.add('active');
    } else {
        area.style.display = 'none';
        if (btn) btn.classList.remove('active');
    }
};

// 保存编辑结果
window.saveTaskResult = async function (stepId) {
    const textarea = document.getElementById(`input-${stepId}`);
    const newVal = textarea.value;
    const btn = document.querySelector(`#edit-area-${stepId} .btn-save`);

    // 禁用按钮防止重复点击
    btn.disabled = true;
    const originalContent = btn.innerHTML;
    btn.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> 保存中...`;

    try {
        const res = await fetch('/api/file/update_task_result', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                process_id: processId,
                step_id: stepId,
                new_summary: newVal
            })
        });

        if (res.ok) {
            btn.innerHTML = `<i class="fa-solid fa-circle-check"></i> 已保存`;
            btn.classList.add('saved');
            setTimeout(() => {
                btn.innerHTML = originalContent;
                btn.classList.remove('saved');
                btn.disabled = false;
            }, 1500);
        } else {
            alert("保存失败");
            btn.disabled = false;
            btn.innerHTML = originalContent;
        }
    } catch (e) {
        console.error(e);
        alert("网络错误");
        btn.disabled = false;
        btn.innerHTML = originalContent;
    }
};

function getStatusText(status) {
    switch (status) {
        case 'processing': return "正在解析...";
        case 'success': return "解析完成";
        case 'failed': return "解析失败";
        default: return "等待中";
    }
}

function getStatusIconHtml(status) {
    if (status === 'processing') {
        return `<div class="status-spinner"><i class="fa-solid fa-circle-notch"></i></div>`;
    } else if (status === 'success') {
        return `<div class="task-icon status-check"><i class="fa-solid fa-check"></i></div>`;
    } else if (status === 'failed') {
        return `<div class="task-icon status-error"><i class="fa-solid fa-xmark"></i></div>`;
    }
    return ``;
}

function finishProcessing() {
    // 显示 "处理完毕" 的提示
    document.getElementById('processing-done-msg').classList.remove('hidden');
    // 显示 "下一步" 按钮
    document.getElementById("nextBtn").classList.remove("hidden");

    // 此时轮询会在 pollStatus 内部被关闭，这里不需要额外操作
}

function addReferenceItem() {
    const container = document.getElementById('reference-list');
    const uniqueId = Date.now() + Math.random().toString(36).substr(2, 5);

    const itemHtml = `
        <div class="reference-card fade-in" id="ref-${uniqueId}">
            <div class="ref-header">
                <span class="ref-title">资料项</span>
                <button type="button" class="btn-remove-icon" onclick="removeRef('${uniqueId}')">
                    <i class="fa-solid fa-trash-can"></i>
                </button>
            </div>
            <div class="ref-grid">
               <div class="col">
                   <label>类型</label>
                   <select class="type-select" onchange="handleTypeChange(this, '${uniqueId}')">
                       <option value="链接">链接</option>
                       <option value="文档">文档</option>
                       <option value="图片">图片</option>
                       <option value="搜索">搜索</option>
                   </select>
               </div>
               <div class="col">
                   <label>可靠度</label>
                   <select>
                       <option>低</option>
                       <option>中</option>
                       <option>高</option>
                       <option>确信</option>
                   </select>
               </div>
            </div>
            <div class="form-group">
                <input type="text" class="ref-url-input" placeholder="请输入 URL 链接">
                <div class="file-upload-wrapper" style="display:none">
                   <input type="file" id="fi-${uniqueId}" class="ref-file-input" 
                          onchange="handleFileSelection(this)">
                   <label for="fi-${uniqueId}" class="custom-file-label">选择文件</label>
                </div>
            </div>
        </div>
    `;
    container.insertAdjacentHTML('beforeend', itemHtml);
}

function removeRef(id) { document.getElementById(`ref-${id}`).remove(); }

function handleTypeChange(sel, id) {
    const card = sel.closest('.reference-card');
    const val = sel.value;
    const urlInput = card.querySelector('.ref-url-input');
    const fileWrapper = card.querySelector('.file-upload-wrapper');
    const fileInput = card.querySelector('.ref-file-input');
    const fileLabel = card.querySelector('.custom-file-label');

    if (val === '链接') {
        // 情况1：链接 -> 显示URL框，隐藏文件框
        urlInput.style.display = 'block';
        fileWrapper.style.display = 'none';
    } else if (val === '搜索') {
        // 情况2：搜索 -> URL框和文件框都隐藏
        urlInput.style.display = 'none';
        fileWrapper.style.display = 'none';
    } else {
        // 情况3：文档 或 图片 -> 隐藏URL框，显示文件框
        urlInput.style.display = 'none';
        fileWrapper.style.display = 'block';

        // 设置对应的文件类型限制
        if (FILE_LIMITS[val]) {
            fileInput.setAttribute('accept', FILE_LIMITS[val].accept);
        }
    }
    fileInput.value = '';
    fileLabel.innerText = '选择文件';
}

function handleFileSelection(input) {
    const file = input.files[0];
    const label = input.nextElementSibling;
    if (!file) {
        label.innerText = '选择文件';
        return;
    }
    const card = input.closest('.reference-card');
    const typeVal = card.querySelector('.type-select').value;
    const limitObj = FILE_LIMITS[typeVal];
    if (limitObj) {
        const fileName = file.name;
        const ext = fileName.slice(((fileName.lastIndexOf(".") - 1) >>> 0) + 2).toLowerCase();
        if (!limitObj.exts.includes(ext)) {
            alert(`格式错误：${limitObj.msg}`);
            input.value = '';
            label.innerText = '选择文件';
            return;
        }
    }
    if (file.size > 10 * 1024 * 1024) {
        alert("文件大小不能超过 10MB");
        input.value = '';
        label.innerText = '选择文件';
        return;
    }
    label.innerText = file.name;
}
