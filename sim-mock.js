// miniprogram/utils/sim-mock.js
/**
 * 强健版本地模拟层（统一状态机 + 科室配置 + 端点补齐）
 * - 统一使用 utils/queue-state-machine.js（唯一真源）
 * - 方案A：允许 “就诊中 -> 已取消”，但仅 super/core（本科室）可操作，并记录reason
 * - 增补科室配置字段与读写端点；保持所有既有端点可用
 */

const { API = {} } = require('../config/endpoints');
const {
  QueueStatus,
  isValidTransition,
  getAllowedTransitions,
  getStatusClass,
  getStatusIcon,
  QueueStateMachine
} = require('./queue-state-machine');

/* -------------------- 基本工具 -------------------- */
const now = () => Date.now();
const sleep = (ms = 80) => new Promise(r => setTimeout(r, ms));
const clone = (v) => JSON.parse(JSON.stringify(v));
const ok = (data) => Promise.resolve(clone(data));
const err = (code, message) => { const e = new Error(message || 'error'); e.code = code || 500; return Promise.reject(e); };
const tryCatch = async (fn) => { try { return await fn(); } catch (e) { return Promise.reject(e && e.code ? e : err(500, e && e.message || 'mock-internal-error')); } };

function normArgs(a, b, c) {
  if (typeof a === 'object' && a !== null) return { url: String(a.url || ''), method: String(a.method || 'GET').toUpperCase(), data: a.data || {} };
  return { url: String(a || ''), method: String((b || 'GET')).toUpperCase(), data: c || {} };
}
function match(url, target) { if (!url || !target) return false; const u = String(url).toLowerCase(); const t = String(target).toLowerCase(); return u === t || u.includes(t); }
function startsWith(url, prefix) { if (!url || !prefix) return false; return String(url).toLowerCase().startsWith(String(prefix).toLowerCase()); }
function toArr(x) { return Array.isArray(x) ? x : (x ? [x] : []); }
function uid(prefix = 'id') { return `${prefix}_${Math.random().toString(36).slice(2, 8)}${Date.now().toString(36).slice(-4)}`; }

function normStatus(s) {
  if (!s) return '等待中';
  const v = String(s).toLowerCase();
  const map = {
    waiting: '等待中', '等待中': '等待中',
    'in-progress': '就诊中', '进行中': '就诊中', '就诊中': '就诊中',
    completed: '已完成', '已完成': '已完成',
    cancelled: '已取消', canceled: '已取消', '已取消': '已取消',
    paused: '已暂停', '已暂停': '已暂停',
    transferred: '已转诊', '已转诊': '已转诊',
    missed: '已错过', '已错过': '已错过',
    urgent: '紧急', '紧急': '紧急'
  };
  return map[v] || s;
}
function normPriority(p) {
  const v = String(p || 'normal').toLowerCase();
  if (['urgent', 'high', 'normal', 'low'].includes(v)) return v;
  if (['紧急', '高', '中', '低'].includes(p)) return ({ '紧急': 'urgent', '高': 'high', '中': 'normal', '低': 'low' })[p];
  return 'normal';
}

/* -------------------- 内存数据 -------------------- */
const T0 = Date.now();
const store = {
  adsText: '欢迎使用智慧医疗系统 - 为您提供专业的医疗服务',
  ads: [
    { id: 'ad1', type: 'banner', text: '三甲专家联诊开通，点击查看', image: '/assets/ads/ad1.png', link: '/pages/ads/index' },
    { id: 'ad2', type: 'banner', text: '在线复诊享绿色通道', image: '/assets/ads/ad2.png', link: '/pages/queue/register/index' }
  ],

  departments: [
    { id: 'd1', name: '消化内科', description: '擅长胃肠疾病、肝病、胰腺疾病的诊断和治疗', open: true,
      specialties: ['胃炎', '胃溃疡', '肝炎', '胰腺炎', '肠易激综合征'], doctors: ['张医生', '李医生', '王主任'], capacity: 50,
      avgConsultationTime: 30, maxDailyPatients: 50,
      workingHours: [{ start: '08:30', end: '12:00' }, { start: '13:30', end: '17:30' }],
      priorityRules: { emergency: 1, vip: 2, normal: 3 }
    },
    { id: 'd2', name: '心血管科', description: '擅长高血压、心脏病、心律失常等心血管疾病的诊疗', open: true,
      specialties: ['高血压', '冠心病', '心律失常', '心力衰竭', '心肌病'], doctors: ['赵医生', '钱主任', '孙教授'], capacity: 40,
      avgConsultationTime: 20, maxDailyPatients: 40,
      workingHours: [{ start: '08:30', end: '12:00' }, { start: '13:30', end: '17:30' }],
      priorityRules: { emergency: 1, vip: 2, normal: 3 }
    },
    { id: 'd3', name: '呼吸科', description: '擅长哮喘、肺炎、慢性阻塞性肺病等呼吸系统疾病', open: true,
      specialties: ['哮喘', '肺炎', 'COPD', '支气管炎', '肺结节'], doctors: ['周医生', '吴主任', '郑教授'], capacity: 35,
      avgConsultationTime: 15, maxDailyPatients: 35,
      workingHours: [{ start: '08:30', end: '12:00' }, { start: '13:30', end: '17:30' }],
      priorityRules: { emergency: 1, vip: 2, normal: 3 }
    },
  ],

  groups: [
    { id:'g1', name:'消化内科专家组', open:true,
      members:[
        {uid:'u_core1', name:'张主任', role:'core', department:'消化内科', specialty:'胃肠疾病'},
        {uid:'u_admin1', name:'李医生', role:'member', department:'消化内科', specialty:'肝病'},
        {uid:'u_admin2', name:'王医生', role:'member', department:'消化内科', specialty:'胰腺疾病'}
      ],
      quota:50, inviteCode:'DIGEST2025', description:'消化内科疾病诊疗专家团队',
      specialties:['胃炎','胃溃疡','肝炎','胰腺炎','肠易激综合征'], createdAt:T0-30*86400000
    },
    { id:'g2', name:'心血管科专家组', open:true,
      members:[
        {uid:'u_core2', name:'钱主任', role:'leader', department:'心血管科', specialty:'冠心病'},
        {uid:'u_admin3', name:'赵医生', role:'member', department:'心血管科', specialty:'高血压'},
        {uid:'u_admin4', name:'孙医生', role:'member', department:'心血管科', specialty:'心律失常'}
      ],
      quota:40, inviteCode:'CARDIO2025', description:'心血管疾病治疗专家团队',
      specialties:['高血压','冠心病','心律失常','心力衰竭','心肌病'], createdAt:T0-25*86400000
    },
    { id:'g3', name:'呼吸科专家组', open:true,
      members:[
        {uid:'u_core3', name:'吴主任', role:'leader', department:'呼吸科', specialty:'哮喘'},
        {uid:'u_admin5', name:'周医生', role:'member', department:'呼吸科', specialty:'肺炎'},
        {uid:'u_admin6', name:'郑医生', role:'member', department:'呼吸科', specialty:'COPD'}
      ],
      quota:35, inviteCode:'RESPIR2025', description:'呼吸系统疾病诊疗专家组',
      specialties:['哮喘','肺炎','COPD','支气管炎','肺结节'], createdAt:T0-20*86400000
    },
  ],

  admins: [
    { uid:'u_core1', name:'张主任', department:'消化内科', groupId:'g1', role:'core' },
    { uid:'u_admin1', name:'李医生', department:'消化内科', groupId:'g1', role:'admin' },
    { uid:'u_admin2', name:'王医生', department:'消化内科', groupId:'g1', role:'admin' },
    { uid:'u_core2', name:'钱主任', department:'心血管科', groupId:'g2', role:'core' },
    { uid:'u_admin3', name:'赵医生', department:'心血管科', groupId:'g2', role:'admin' },
    { uid:'u_admin4', name:'孙医生', department:'心血管科', groupId:'g2', role:'admin' },
    { uid:'u_core3', name:'吴主任', department:'呼吸科', groupId:'g3', role:'core' },
    { uid:'u_admin5', name:'周医生', department:'呼吸科', groupId:'g3', role:'admin' },
    { uid:'u_admin6', name:'郑医生', department:'呼吸科', groupId:'g3', role:'admin' },
  ],

  patients: [
    { id:1, name:'张三', sex:'男', age:45, phone:'13800138001', disease:'慢性胃炎', status:'等待入院', groupId:'g1', departmentId:'d1', departmentName:'消化内科',
      idCard:'110101198001011234', address:'北京市朝阳区建国门外大街1号', emergencyContact:'李四', emergencyMobile:'13900139001',
      medicalHistory:'慢性胃炎病史3年，反复发作', allergies:'青霉素过敏', createdAt:'2025-01-15', archived:false },
    { id:2, name:'李四', sex:'女', age:38, phone:'13800138002', disease:'胃溃疡', status:'在院治疗', groupId:'g1', departmentId:'d1', departmentName:'消化内科',
      idCard:'110101198701022345', address:'北京市海淀区中关村大街15号', emergencyContact:'王五', emergencyMobile:'13900139002',
      medicalHistory:'胃溃疡病史1年，近期加重', allergies:'无', createdAt:'2025-02-10', archived:false },
    { id:3, name:'王五', sex:'男', age:52, phone:'13800138003', disease:'肝炎', status:'门诊随访', groupId:'g1', departmentId:'d1', departmentName:'消化内科',
      idCard:'110101197301033456', address:'北京市西城区西长安街10号', emergencyContact:'赵六', emergencyMobile:'13900139003',
      medicalHistory:'乙型肝炎病史5年，定期复查', allergies:'头孢过敏', createdAt:'2025-03-05', archived:true },
    { id:4, name:'赵六', sex:'男', age:65, phone:'13800138004', disease:'高血压', status:'等待入院', groupId:'g2', departmentId:'d2', departmentName:'心血管科',
      idCard:'110101196001044567', address:'北京市东城区东长安街20号', emergencyContact:'钱七', emergencyMobile:'13900139004',
      medicalHistory:'高血压病史10年，药物控制', allergies:'无', createdAt:'2025-01-20', archived:false },
    { id:5, name:'钱七', sex:'女', age:58, phone:'13800138005', disease:'冠心病', status:'在院治疗', groupId:'g2', departmentId:'d2', departmentName:'心血管科',
      idCard:'110101196701055678', address:'北京市丰台区丰台路30号', emergencyContact:'孙八', emergencyMobile:'13900139005',
      medicalHistory:'冠心病病史3年，支架术后', allergies:'阿司匹林过敏', createdAt:'2025-02-15', archived:false },
    { id:6, name:'孙八', sex:'男', age:48, phone:'13800138006', disease:'心律失常', status:'门诊随访', groupId:'g2', departmentId:'d2', departmentName:'心血管科',
      idCard:'110101197701066789', address:'北京市石景山区石景山路40号', emergencyContact:'周九', emergencyMobile:'13900139006',
      medicalHistory:'心律失常病史2年，药物治疗', allergies:'无', createdAt:'2025-03-10', archived:true },
    { id:7, name:'周九', sex:'女', age:35, phone:'13800138007', disease:'哮喘', status:'等待入院', groupId:'g3', departmentId:'d3', departmentName:'呼吸科',
      idCard:'110101199001077890', address:'北京市昌平区昌平路50号', emergencyContact:'吴十', emergencyMobile:'13900139007',
      medicalHistory:'哮喘病史8年，季节性发作', allergies:'花粉过敏', createdAt:'2025-01-25', archived:false },
    { id:8, name:'吴十', sex:'男', age:42, phone:'13800138008', disease:'肺炎', status:'在院治疗', groupId:'g3', departmentId:'d3', departmentName:'呼吸科',
      idCard:'110101198301088901', address:'北京市通州区通州路60号', emergencyContact:'郑十一', emergencyMobile:'13900139008',
      medicalHistory:'肺炎急性发作，需要住院治疗', allergies:'青霉素过敏', createdAt:'2025-02-20', archived:false },
    { id:9, name:'郑十一', sex:'女', age:29, phone:'13800138009', disease:'支气管炎', status:'门诊随访', groupId:'g3', departmentId:'d3', departmentName:'呼吸科',
      idCard:'110101199601099012', address:'北京市大兴区大兴路70号', emergencyContact:'冯十二', emergencyMobile:'13900139009',
      medicalHistory:'慢性支气管炎病史4年', allergies:'无', createdAt:'2025-03-15', archived:true },
  ],

  inquiries: [
    { id:'inq_1', userId:'1', fromId:'1', fromName:'张三', fromRole:'patient', title:'胃炎症状咨询',
      content:'医生您好，我最近胃痛加重，饭后胀痛明显，需要调整用药吗？',
      createdAt: T0-3600*1000, status:'open', important:false, replies:[], groupId:'g1', departmentId:'d1' },
    { id:'inq_2', userId:'2', fromId:'2', fromName:'李四', fromRole:'patient', title:'胃溃疡复查',
      content:'胃溃疡治疗后需要多久复查一次胃镜？',
      createdAt: T0-7200*1000, status:'open', important:true, replies:[], groupId:'g1', departmentId:'d1' },
    { id:'inq_3', userId:'3', fromId:'3', fromName:'王五', fromRole:'patient', title:'肝炎肝功能',
      content:'肝功能检查结果出来了，请帮忙看一下是否正常',
      createdAt: T0-10800*1000, status:'open', important:false, replies:[], groupId:'g1', departmentId:'d1' },
  ],

  pInquiries: [
    { id:'q1', userId:'1', title:'胃炎饮食咨询', content:'胃炎患者饮食需要注意什么？哪些食物要避免？',
      createdAt: T0-7200*1000, replies:[], groupId:'g1', status: '待回复' }
  ],

  tasks: [
    { id:'t1', title:'每日巡检', status:'open', assignee:'u_admin1', createdAt:T0-86400000, dueAt:T0+3*86400000 },
  ],
  messages: [
    { id:'m1', type:'system', content:'欢迎使用系统', createdAt:T0-3600*1000 },
  ],

  adminProfiles: {
    u_admin1: { id:'u_admin1', name:'李医生', departmentId:'d1', groupId:'g1', role:'admin', email:'li@example.com' }
  },

  bindings: {},
  invites: [],
  transfers: [],

  queues: [
    {
      id: 'queue_1',
      name: '消化内科排队队列',
      departmentId: 'd1',
      departmentName: '消化内科',
      groupId: 'g1',
      groupName: '消化内科专家组',
      currentNumber: 15,
      waitingCount: 3,
      estimatedTime: '约45分钟',
      status: 'active',
      createdAt: T0 - 2 * 3600 * 1000,
      items: [
        {
          id: 'q_item_1',
          patientId: 1,
          patientName: '张三',
          number: 15,
          status: '等待中',
          priority: 'normal',
          department: '消化内科',
          departmentId: 'd1',
          groupId: 'g1',
          createdAt: T0 - 90 * 60 * 1000,
          expectedTime: T0 + 45 * 60 * 1000,
          transitionHistory: [{ from: null, to: '等待中', operator: 'system', timestamp: T0 - 90 * 60 * 1000, reason: '加入队列' }]
        },
        {
          id: 'q_item_2',
          patientId: 2,
          patientName: '李四',
          number: 16,
          status: '就诊中',
          priority: 'normal',
          department: '消化内科',
          departmentId: 'd1',
          groupId: 'g1',
          createdAt: T0 - 75 * 60 * 1000,
          startedAt: T0 - 15 * 60 * 1000,
          expectedTime: T0 + 30 * 60 * 1000,
          transitionHistory: [
            { from: null, to: '等待中', operator: 'system', timestamp: T0 - 75 * 60 * 1000, reason: '加入队列' },
            { from: '等待中', to: '就诊中', operator: 'doctor_1', timestamp: T0 - 15 * 60 * 1000, reason: '开始就诊' }
          ]
        },
        {
          id: 'q_item_3',
          patientId: 3,
          patientName: '王五',
          number: 17,
          status: '已完成',
          priority: 'normal',
          department: '消化内科',
          departmentId: 'd1',
          groupId: 'g1',
          createdAt: T0 - 120 * 60 * 1000,
          startedAt: T0 - 60 * 60 * 1000,
          completedAt: T0 - 30 * 60 * 1000,
          expectedTime: T0,
          transitionHistory: [
            { from: null, to: '等待中', operator: 'system', timestamp: T0 - 120 * 60 * 1000, reason: '加入队列' },
            { from: '等待中', to: '就诊中', operator: 'doctor_1', timestamp: T0 - 60 * 60 * 1000, reason: '开始就诊' },
            { from: '就诊中', to: '已完成', operator: 'doctor_1', timestamp: T0 - 30 * 60 * 1000, reason: '就诊完成' }
          ]
        }
      ]
    },
    {
      id: 'queue_2',
      name: '心血管科排队队列',
      departmentId: 'd2',
      departmentName: '心血管科',
      groupId: 'g2',
      groupName: '心血管科专家组',
      currentNumber: 18,
      waitingCount: 2,
      estimatedTime: '约30分钟',
      status: 'active',
      createdAt: T0 - 1.5 * 3600 * 1000,
      items: [
        {
          id: 'q_item_4',
          patientId: 4,
          patientName: '赵六',
          number: 18,
          status: '等待中',
          priority: 'high',
          department: '心血管科',
          departmentId: 'd2',
          groupId: 'g2',
          createdAt: T0 - 60 * 60 * 1000,
          expectedTime: T0 + 30 * 60 * 1000,
          transitionHistory: [{ from: null, to: '等待中', operator: 'system', timestamp: T0 - 60 * 60 * 1000, reason: '加入队列' }]
        },
        {
          id: 'q_item_5',
          patientId: 5,
          patientName: '钱七',
          number: 19,
          status: '就诊中',
          priority: 'normal',
          department: '心血管科',
          departmentId: 'd2',
          groupId: 'g2',
          createdAt: T0 - 45 * 60 * 1000,
          startedAt: T0 - 20 * 60 * 1000,
          expectedTime: T0 + 10 * 60 * 1000,
          transitionHistory: [
            { from: null, to: '等待中', operator: 'system', timestamp: T0 - 45 * 60 * 1000, reason: '加入队列' },
            { from: '等待中', to: '就诊中', operator: 'doctor_2', timestamp: T0 - 20 * 60 * 1000, reason: '开始就诊' }
          ]
        }
      ]
    },
    {
      id: 'queue_3',
      name: '呼吸科排队队列',
      departmentId: 'd3',
      departmentName: '呼吸科',
      groupId: 'g3',
      groupName: '呼吸科专家组',
      currentNumber: 20,
      waitingCount: 1,
      estimatedTime: '约15分钟',
      status: 'active',
      createdAt: T0 - 1 * 3600 * 1000,
      items: [
        {
          id: 'q_item_6',
          patientId: 7,
          patientName: '周九',
          number: 20,
          status: '等待中',
          priority: 'normal',
          department: '呼吸科',
          departmentId: 'd3',
          groupId: 'g3',
          createdAt: T0 - 30 * 60 * 1000,
          expectedTime: T0 + 15 * 60 * 1000,
          transitionHistory: [{ from: null, to: '等待中', operator: 'system', timestamp: T0 - 30 * 60 * 1000, reason: '加入队列' }]
        },
        {
          id: 'q_item_7',
          patientId: 8,
          patientName: '吴十',
          number: 21,
          status: '就诊中',
          priority: 'urgent',
          department: '呼吸科',
          departmentId: 'd3',
          groupId: 'g3',
          createdAt: T0 - 25 * 60 * 1000,
          startedAt: T0 - 10 * 60 * 1000,
          expectedTime: T0 + 5 * 60 * 1000,
          transitionHistory: [
            { from: null, to: '等待中', operator: 'system', timestamp: T0 - 25 * 60 * 1000, reason: '加入队列' },
            { from: '等待中', to: '就诊中', operator: 'doctor_3', timestamp: T0 - 10 * 60 * 1000, reason: '开始就诊' }
          ]
        }
      ]
    }
  ]
};

/* -------------------- 队列辅助 & 统计 -------------------- */
function canTransit(from, to) { return isValidTransition(normStatus(from), normStatus(to)); }
function findQueueItemById(itemId) {
  for (const q of store.queues) {
    const hit = q.items.find(it => String(it.id) === String(itemId));
    if (hit) return { queue: q, item: hit };
  }
  return { queue: null, item: null };
}
function getDeptById(id) { return store.departments.find(d => String(d.id) === String(id)) || null; }
function computeQueueStats(filter = {}) {
  const { departmentId, groupId } = filter;
  let total = 0, waiting = 0, inProgress = 0, completed = 0, cancelled = 0, paused = 0, urgent = 0;
  let waitSumMinutes = 0;
  store.queues.forEach(q => {
    if (departmentId && String(q.departmentId) !== String(departmentId)) return;
    if (groupId && String(q.groupId) !== String(groupId)) return;
    const dept = getDeptById(q.departmentId);
    const avgMin = dept?.avgConsultationTime || 30;
    q.items.forEach(it => {
      total++;
      const s = normStatus(it.status);
      if (s === '等待中') { waiting++; waitSumMinutes += avgMin; }
      else if (s === '就诊中') inProgress++;
      else if (s === '已完成') completed++;
      else if (s === '已取消') cancelled++;
      else if (s === '已暂停') paused++;
      if (normPriority(it.priority) === 'urgent') urgent++;
    });
  });
  const averageWaitMinutes = waitSumMinutes;
  return { total, waiting, inProgress, completed, cancelled, paused, urgent, averageWaitMinutes };
}

/* -------------------- 业务实现（handlers） -------------------- */
const handlers = {
  async login({ account, password }) {
    const acc = String(account || '').trim();
    const isPhone = /^1[3-9]\d{9}$/.test(acc);
    const adminMap = {
      zhang: { uid:'u_core1',  name:'张主任',   role:'core',  groupId:'g1', departmentId:'d1' },
      li:    { uid:'u_admin1', name:'李医生',   role:'admin', groupId:'g1', departmentId:'d1' },
      wang:  { uid:'u_admin2', name:'王医生',   role:'admin', groupId:'g1', departmentId:'d1' },
      qian:  { uid:'u_core2',  name:'钱主任',   role:'core',  groupId:'g2', departmentId:'d2' },
      zhao:  { uid:'u_admin3', name:'赵医生',   role:'admin', groupId:'g2', departmentId:'d2' },
      sun:   { uid:'u_admin4', name:'孙医生',   role:'admin', groupId:'g2', departmentId:'d2' },
      wu:    { uid:'u_core3',  name:'吴主任',   role:'core',  groupId:'g3', departmentId:'d3' },
      zhou:  { uid:'u_admin5', name:'周医生',   role:'admin', groupId:'g3', departmentId:'d3' },
      zheng: { uid:'u_admin6', name:'郑医生',   role:'admin', groupId:'g3', departmentId:'d3' },
      super: { uid:'u_super1', name:'超级管理员',role:'super', groupId:null, departmentId:null },
    };
    const key = acc.toLowerCase();
    if (adminMap[key]) return ok(buildSession({ id: adminMap[key].uid, name: adminMap[key].name, role: adminMap[key].role, groupId: adminMap[key].groupId, departmentId: adminMap[key].departmentId }));
    if (isPhone) {
      const p = store.patients.find(x => x.phone === acc);
      if (p) return ok(buildSession({ id:'p'+p.id, name:p.name, role:'patient', groupId:p.groupId, departmentId:p.departmentId }));
      return ok(buildSession({ id:'p_default', name:'测试患者', role:'patient', groupId:'g1', departmentId:'d1' }));
    }
    return ok(buildSession({ id:'u_admin_default', name: acc || '管理员', role:'admin', groupId:'g1', departmentId:'d1' }));
  },
  async wxLogin({ code }) { return ok(buildSession({ id:'u_wx_1', name:'微信用户', role:'patient', groupId:'g1', departmentId:'d1' })); },
  async userProfileGet({ token }) { const any = store.adminProfiles['u_admin1'] || null; return ok({ user: any }); },
  async userProfileUpdate(payload) { return ok({ success:true, profile: payload }); },
  async changePassword() { return ok({ success:true }); },
  async userRegister() { return ok({ success:true, userId: uid('user') }); },

  /** 患者 */
  async patientsList({ keyword, departmentId } = {}) {
    let list = clone(store.patients);
    if (keyword) list = list.filter(p => (p.name && p.name.includes(keyword)) || (p.phone && p.phone.includes(keyword)));
    if (departmentId) list = list.filter(p => String(p.departmentId) === String(departmentId));
    return list;
  },
  async patientDetail({ id }) { return store.patients.find(x => String(x.id) === String(id)) || null; },
  async patientsExport() { return { url:'/mock/export/patients.csv', generatedAt: now() }; },
  async patientArchive({ id, archived }) { const p = store.patients.find(x => String(x.id) === String(id)); if (!p) return err(404,'患者不存在'); p.archived = !!archived; return { success:true, patient: p }; },
  async patientCheckArchive({ id }) { const p = store.patients.find(x => String(x.id) === String(id)); return { archived: !!p?.archived }; },
  async patientRegister(payload) { const p = { id: store.patients.length + 1, ...payload, createdAt: new Date().toISOString(), archived:false }; store.patients.push(p); return { success:true, patient: p }; },

  /** 科室/绑定 */
  async departments() { return clone(store.departments); },
  async departmentDetail({ id }) {
    const d = store.departments.find(x => String(x.id) === String(id));
    if (!d) return null;
    const doctors = (d.doctors || []).map((name, idx) => ({
      id: `doc_${d.id}_${idx+1}`,
      name,
      title: idx===0?'主任医师':(idx===1?'副主任医师':'主治医师'),
      bio: `${d.name} ${name}，擅长：${(d.specialties||[])[idx % (d.specialties||['综合']).length]}`
    }));
    return { ...clone(d), doctors };
  },
  async departmentMembers({ id }) { const g = store.groups.find(x => x.id === `g${String(id).slice(-1)}`) || store.groups[0]; return g ? clone(g.members) : []; },
  async departmentAdmins({ id }) { const admins = store.admins.filter(a => String(a.groupId) === `g${String(id).slice(-1)}`); return clone(admins); },
  async addDepartmentAdmin({ name, departmentId, role='admin' }) {
    const newAdmin = { uid: uid('u_admin'), name: name || '新管理员', department: departmentId, groupId: `g${String(departmentId).slice(-1)}`, role };
    store.admins.push(newAdmin);
    return { success:true, admin: newAdmin };
  },
  async removeDepartmentAdmin({ uid: rid }) { const i = store.admins.findIndex(x => x.uid === rid); if (i >= 0) store.admins.splice(i, 1); return { success:true }; },
  async userBindDepartment({ userId, departmentId, groupId }) { store.bindings[userId] = { departmentId, groupId, bindTime: now() }; return { success:true, binding: store.bindings[userId] }; },
  async checkDepartmentBinding({ userId }) { return store.bindings[userId] || null; },
  async userAvailableDepartments() { return clone(store.departments); },

  /** ★ 新增：科室创建 & 配置读写（Mock） */
  async createDepartment({ name, description }) {
    const id = `d${store.departments.length + 1}`;
    const dept = {
      id, name: name || '新科室', description: description || '', open: true,
      specialties: [], doctors: [], capacity: 30,
      avgConsultationTime: 30, maxDailyPatients: 30,
      workingHours: [{ start:'08:30', end:'12:00' }, { start:'13:30', end:'17:30' }],
      priorityRules: { emergency:1, vip:2, normal:3 }
    };
    store.departments.push(dept);
    return { success:true, department: dept };
  },
  async getDepartmentConfig({ id }) {
    const d = getDeptById(id);
    if (!d) return err(404, '科室不存在');
    const cfg = (({ avgConsultationTime, maxDailyPatients, workingHours, priorityRules }) =>
      ({ avgConsultationTime, maxDailyPatients, workingHours, priorityRules }))(d);
    return { id: d.id, ...cfg };
  },
  async updateDepartmentConfig({ id, config, role, boundDeptId }) {
    const d = getDeptById(id);
    if (!d) return err(404, '科室不存在');
    const r = String(role || '').toLowerCase();
    const allow = r === 'super' || (r === 'core' && String(boundDeptId) === String(id));
    if (!allow) return err(403, '无权修改科室配置');
    Object.assign(d, config || {});
    return { success:true, department: d };
  },

  /** 广告 / 问询 / 组 / 任务 / 消息（略，保持原样） */
  async ads() { return { list: clone(store.ads) }; },
  async adsUpdate({ id, ...rest }) { const ad = store.ads.find(x => x.id === id); if (ad) Object.assign(ad, rest); return { success:true, ad: ad || null }; },
  async adsDelete({ id }) { const i = store.ads.findIndex(x => x.id === id); if (i >= 0) store.ads.splice(i, 1); return { success:true }; },

  async inquiries() { return clone(store.inquiries); },
  async inquiryReply({ id, content, replier='admin_mock' }) { const q = store.inquiries.find(x => x.id === id); if (!q) return err(404,'问询不存在'); q.replies.push({ id: uid('reply'), content, replier, createdAt: now() }); return { success:true, inquiry: q }; },
  async inquiryMark({ id, important }) { const q = store.inquiries.find(x => x.id === id); if (!q) return err(404,'问询不存在'); q.important = !!important; return { success:true, inquiry: q }; },
  async inquiryResolve({ id }) { const q = store.inquiries.find(x => x.id === id); if (!q) return err(404,'问询不存在'); q.status = 'resolved'; return { success:true, inquiry: q }; },

  async patientInquiryList({ userId }) { return clone(store.pInquiries.filter(x => !userId || x.userId === userId)); },
  async patientInquiryCreate({ title, content, userId, groupId='g1' }) { const item = { id: uid('q'), title, content, userId, createdAt: now(), replies:[], groupId, status:'待回复' }; store.pInquiries.unshift(item); return { success:true, item }; },
  async patientInquiryDetail({ id }) { return clone(store.pInquiries.find(x => x.id === id) || null); },
  async patientInquiryReply({ id, content, replier='doctor_mock' }) { const q = store.pInquiries.find(x => x.id === id); if (!q) return err(404,'问询不存在'); q.replies.push({ id: uid('reply'), content, replier, createdAt: now() }); q.status = '已回复'; return { success:true, inquiry: q }; },

  async groups() { return clone(store.groups); },
  async groupCreate({ name='新专家组', quota=30, inviteCode, description='' }) { const g = { id: uid('g'), name, open:true, members:[], quota, inviteCode:(inviteCode||uid('INV')).toUpperCase(), description, specialties:[], createdAt: now() }; store.groups.push(g); return { success:true, group: g }; },
  async groupOpen({ id, open }) { const g = store.groups.find(x => String(x.id) === String(id)); if (g) g.open = !!open; return { success:true, group: g || null }; },
  async groupSetQuota({ id, quota }) { const g = store.groups.find(x => String(x.id) === String(id)); if (g) g.quote = Number(quota) || g.quota; return { success:true, group: g || null }; },
  async groupAddMember({ groupId, member }) { const g = store.groups.find(x => x.id === groupId); if (!g) return err(404,'组不存在'); const m = { uid: member?.uid||uid('u'), name: member?.name||'新成员', role: member?.role||'member', department: member?.department||'', specialty: member?.specialty||'' }; g.members.push(m); return { success:true, group:g, member:m }; },
  async groupRemoveMember({ groupId, uid:rm }) { const g = store.groups.find(x => x.id === groupId); if (!g) return err(404,'组不存在'); g.members = g.members.filter(x => x.uid !== rm); return { success:true, group:g }; },
  async groupSetLeader({ groupId, uid }) { const g = store.groups.find(x => x.id === groupId); if (!g) return err(404,'组不存在'); g.members.forEach(m => { if (m.role === 'leader') m.role = 'member'; }); const mm = g.members.find(m => m.uid === uid); if (mm) mm.role = 'leader'; return { success:true, group:g }; },
  async groupSetRole({ groupId, uid, role }) { const g = store.groups.find(x => x.id === groupId); if (!g) return err(404,'组不存在'); const mm = g.members.find(m => m.uid === uid); if (mm) mm.role = role || mm.role; return { success:true, group:g }; },
  async groupAddFromPool({ groupId, poolId }) { const g = store.groups.find(x => x.id === groupId); if (!g) return err(404,'组不存在'); const m = { uid: uid('u'), name:`成员_${poolId||'pool'}`, role:'member', department:'', specialty:'' }; g.members.push(m); return { success:true, group:g, member:m }; },
  async groupJoinByCode({ code, userId }) { const g = store.groups.find(x => x.inviteCode === code); if (!g) return err(404,'邀请码无效'); store.bindings[userId] = { departmentId:`d${g.id.slice(-1)}`, groupId:g.id, bindTime: now() }; return { success:true, binding: store.bindings[userId] }; },
  async groupConfirmBinding({ userId, departmentId, groupId }) { store.bindings[userId] = { departmentId, groupId, bindTime: now() }; return { success:true, binding: store.bindings[userId] }; },
  async groupCurrentBinding({ userId }) { return store.bindings[userId] || null; },
  async groupUnbind({ userId }) { delete store.bindings[userId]; return { success:true }; },

  async messages() { return clone(store.messages); },
  async patientMessages({ userId }) { return clone(store.messages.filter(m => !userId || m.userId === userId)); },

  async tasksList() { return clone(store.tasks); },
  async taskCreate({ title='新任务', assignee=null, dueAt=null }) { const t = { id: uid('t'), title, status:'open', assignee, createdAt: now(), dueAt }; store.tasks.push(t); return { success:true, task: t }; },
  async taskDetail({ id }) { return clone(store.tasks.find(x => x.id === id) || null); },

  async adminProfileGet() { const any = store.adminProfiles['u_admin1'] || { id:'u_admin1', name:'李医生', departmentId:'d1', groupId:'g1', role:'admin', email:'li@example.com' }; return clone(any); },
  async adminProfileUpdate(payload) { const id = payload?.id || 'u_admin1'; store.adminProfiles[id] = { ...(store.adminProfiles[id] || {}), ...payload }; return { success:true, profile: store.adminProfiles[id] }; },
  async adminUpdate() { return { success:true }; },
  async reportLog() { return { success:true, loggedAt: now() }; },
  async grant() { return { success:true, granted:true }; },

  async inviteCreate({ code, groupId='g1', departmentId='d1', creator='u_admin1' }) { const inv = { id: uid('inv'), code:(code||uid('INV')).toUpperCase(), groupId, departmentId, creator, status:'active', createdAt: now() }; store.invites.push(inv); return { success:true, invite: inv }; },
  async invitesList() { return clone(store.invites); },
  async bindByInvite({ code, userId }) { const inv = store.invites.find(x => x.code === String(code).toUpperCase() && x.status === 'active'); if (!inv) return err(404,'邀请码无效'); store.bindings[userId] = { departmentId: inv.departmentId, groupId: inv.groupId, bindTime: now() }; inv.status = 'used'; return { success:true, binding: store.bindings[userId] }; },
  async transferCreate({ fromGroup, toGroup, patientId }) { const tr = { id: uid('tr'), fromGroup, toGroup, patientId, status:'pending', createdAt: now() }; store.transfers.push(tr); return { success:true, transfer: tr }; },
  async transferList() { return clone(store.transfers); },

  /** 患者查询（带科室隔离） */
  async patientDetailByDeptName(params = {}) {
    const { deptId, name, role, boundDeptId } = params;
    if (!deptId || !name) return err(400, '缺少必要参数');
    const roleNorm = String(role || '').toLowerCase();
    if (roleNorm === 'admin' || roleNorm === 'core') {
      if (!boundDeptId || String(boundDeptId) !== String(deptId)) return err(403, '无权限访问该科室患者');
    }
    const list = Array.isArray(store.patients) ? store.patients : (Array.isArray(store.patientList) ? store.patientList : []);
    const q = String(name).replace(/\s+/g, '').toLowerCase();
    const target = list.find(p => {
      const n = (p.name || p.realname || p.patientName || '').replace(/\s+/g, '').toLowerCase();
      const pdid = String(
        p.departmentId || p.deptId || p.dept_id ||
        (p.department && (p.department.id || p.department.departmentId || p.department.deptId)) ||
        (p.patient && p.patient.department && (p.patient.department.id || p.patient.department.departmentId)) || ''
      );
      return pdid === String(deptId) && n === q;
    });
    if (!target) return err(404, '未找到该患者');
    return ok(target);
  },

  /** 队列全链路 */
  async queueStatus() {
    return [
      { value:'等待中', code:'waiting' },
      { value:'就诊中', code:'in-progress' },
      { value:'已完成', code:'completed' },
      { value:'已取消', code:'cancelled' },
      { value:'已暂停', code:'paused' },
      { value:'紧急',   code:'urgent' }
    ];
  },
  async adminQueueListAll({ deptId, departmentId, groupId, page=1, size=20 } = {}) {
    const dept = departmentId || deptId || null;
    const gid = groupId || null;
    let list = store.queues.filter(q => (!dept || String(q.departmentId)===String(dept)) && (!gid || String(q.groupId)===String(gid)));
    const start = (Number(page)-1) * Number(size);
    return clone(list.slice(start, start + Number(size)));
  },
  async queueList() { return clone(store.queues); },
  async queueDetail({ id }) { return clone(store.queues.find(x => String(x.id) === String(id)) || null); },
  async queueItemDetail({ id }) { const { item } = findQueueItemById(id); return clone(item || null); },

  // ★ 状态变更（统一状态机；方案A权限：就诊中→已取消仅 super 或本部门 core）
  async queueItemUpdateStatus({ id, status, reason='管理员操作', operator='admin_mock', role, boundDeptId }) {
    const target = findQueueItemById(id);
    if (!target.item) return err(404,'队列项不存在');

    const from = normStatus(target.item.status);
    const to = normStatus(status);

    if (from === '就诊中' && to === '已取消') {
      const r = String(role || '').toLowerCase();
      const allow = (r === 'super') || (r === 'core' && String(boundDeptId) === String(target.item.departmentId));
      if (!allow) return err(403, '无权在就诊中直接取消');
    }

    if (!canTransit(from, to)) return err(400, `不允许从「${from}」到「${to}」`);

    const sm = new QueueStateMachine();
    const updated = sm.transition(target.item, to, operator, reason);
    if (to === '就诊中') target.queue.currentNumber = updated.number || target.queue.currentNumber;
    if (to === '已完成' || to === '已取消') {
      target.queue.waitingCount = Math.max(0, (target.queue.waitingCount || 0) - 1);
    }
    return { success:true, item: updated };
  },

  async queueItemSetPriority({ id, priority }) {
    const target = findQueueItemById(id);
    if (!target.item) return err(404,'队列项不存在');
    target.item.priority = normPriority(priority);
    target.item.updatedAt = now();
    return { success:true, item: target.item };
  },

  async adminQueueStats({ deptId, departmentId, groupId }) { return computeQueueStats({ departmentId: departmentId || deptId || null, groupId }); },
  async adminQueueBroadcast({ message = '队列状态已更新，请关注排队信息。' }) { return { success:true, sentAt: now(), message }; }
};

/* -------------------- 登录会话构造 -------------------- */
function buildSession({ id, name, role, groupId = null, departmentId = null }) {
  const sess = { token: `mock-token-${id}-${Date.now()}`, role, user: { id, name, role, groupId, departmentId }, expires_in: 7200 };
  if (groupId && departmentId) {
    const g = store.groups.find(x => x.id === groupId);
    const d = store.departments.find(x => x.id === departmentId);
    if (g && d) {
      sess.groupBinding = { groupId, groupName: g.name, departmentId, departmentName: d.name, inviteCode: g.inviteCode, bindTime: now() };
    }
  }
  return sess;
}

/* -------------------- 路由映射 -------------------- */
const routes = [
  // 认证
  { key:'login',          test:(u,m)=>match(u,API.login)&&m==='POST',               call:({data})=>handlers.login({account:data?.account||data?.username, password:data?.password}) },
  { key:'wxLogin',        test:(u,m)=>match(u,API.wxLogin)&&m==='POST',             call:({data})=>handlers.wxLogin({code:data?.code}) },

  // 资料
  { key:'userProfileGet', test:(u,m)=>match(u,API.userProfileGet)&&m==='GET',       call:({data})=>handlers.userProfileGet({token:data?.token}) },
  { key:'userProfileUpdate', test:(u,m)=>match(u,API.userProfileUpdate)&&m==='POST',call:({data})=>handlers.userProfileUpdate(data) },
  { key:'changePassword', test:(u,m)=>match(u,API.changePassword)&&m==='POST',      call:()=>handlers.changePassword() },
  { key:'userRegister',   test:(u,m)=>match(u,API.userRegister)&&m==='POST',        call:({data})=>handlers.userRegister(data) },

  // 患者
  { key:'patients',       test:(u,m)=>match(u,API.patients)&&m==='GET',             call:({data})=>handlers.patientsList(data) },
  { key:'patientDetailByDeptName', test:(u,m)=>match(u, API.patientDetailByDeptName)&&m==='GET', call:({ data }) => handlers.patientDetailByDeptName(data) },
  { key:'patientDetail',  test:(u,m)=>startsWith(u,'/api/patients/')&&m==='GET',    call:({url})=>handlers.patientDetail({id:url.split('/').pop()}) },
  { key:'patientsExport', test:(u,m)=>match(u,API.patientsExport)&&m==='GET',       call:()=>handlers.patientsExport() },
  { key:'patientArchive', test:(u,m)=>startsWith(u,'/api/patients/')&&u.includes('/archive')&&m==='POST', call:({url,data})=>handlers.patientArchive({id:url.split('/')[3], archived:data?.archived}) },
  { key:'patientCheckArchive', test:(u,m)=>startsWith(u,'/api/patients/')&&u.includes('/check-archive')&&m==='GET', call:({url})=>handlers.patientCheckArchive({id:url.split('/')[3]}) },
  { key:'patientRegister', test:(u,m)=>match(u,API.patientRegister)&&m==='POST',    call:({data})=>handlers.patientRegister(data) },

  // 科室/绑定（含新增）
  { key:'departments',    test:(u,m)=>match(u,API.departments)&&m==='GET',          call:()=>handlers.departments() },
  { key:'departmentCreate', test:(u,m)=>match(u,API.departments)&&m==='POST',       call:({data})=>handlers.createDepartment(data) },
  { key:'departmentDetail', test:(u,m)=>match(u,API.departmentDetail)&&m==='GET',   call:({data})=>handlers.departmentDetail({id:data?.id}) },
  { key:'departmentMembers', test:(u,m)=>match(u,API.departmentMembers)&&m==='GET', call:({data})=>handlers.departmentMembers({id:data?.id}) },
  { key:'departmentAdmins', test:(u,m)=>match(u,API.departmentAdmins)&&m==='GET',   call:({data})=>handlers.departmentAdmins({id:data?.id}) },
  { key:'addDepartmentAdmin', test:(u,m)=>match(u,API.addDepartmentAdmin)&&m==='POST', call:({data})=>handlers.addDepartmentAdmin(data) },
  { key:'removeDepartmentAdmin', test:(u,m)=>match(u,API.removeDepartmentAdmin)&&m==='POST', call:({data})=>handlers.removeDepartmentAdmin(data) },
  { key:'userBindDepartment', test:(u,m)=>match(u,API.userBindDepartment)&&m==='POST', call:({data})=>handlers.userBindDepartment(data) },
  { key:'checkDepartmentBinding', test:(u,m)=>match(u,API.checkDepartmentBinding)&&m==='GET', call:({data})=>handlers.checkDepartmentBinding(data) },
  { key:'userAvailableDepartments', test:(u,m)=>match(u,API.userAvailableDepartments)&&m==='GET', call:()=>handlers.userAvailableDepartments() },

  // ★ 科室配置
  { key:'departmentConfigGet', test:(u,m)=> (match(u,API.departmentConfig)||u.includes('/api/departments/config')) && m==='GET', call:({data})=>handlers.getDepartmentConfig({ id: data?.id }) },
  { key:'departmentConfigUpdate', test:(u,m)=> (match(u,API.departmentConfig)||u.includes('/api/departments/config')) && m==='PUT', call:({data})=>handlers.updateDepartmentConfig({ id: data?.id, config: data?.config, role: data?.role, boundDeptId: data?.boundDeptId }) },

  // 广告
  { key:'ads',            test:(u,m)=>match(u,API.ads)&&m==='GET',                  call:()=>handlers.ads() },
  { key:'adsUpdate',      test:(u,m)=>match(u,API.adsUpdate)&&m==='POST',           call:({data})=>handlers.adsUpdate(data) },
  { key:'adsDelete',      test:(u,m)=>match(u,API.adsDelete)&&m==='POST',           call:({data})=>handlers.adsDelete(data) },

  // 问询（管理端）
  { key:'inquiries',      test:(u,m)=>match(u,API.inquiries)&&m==='GET',            call:()=>handlers.inquiries() },
  { key:'inquiryReply',   test:(u,m)=>match(u,API.inquiryReply)&&m==='POST',        call:({data})=>handlers.inquiryReply(data) },
  { key:'inquiryMark',    test:(u,m)=>match(u,API.inquiryMark)&&m==='POST',         call:({data})=>handlers.inquiryMark(data) },
  { key:'inquiryResolve', test:(u,m)=>match(u,API.inquiryResolve)&&m==='POST',      call:({data})=>handlers.inquiryResolve(data) },

  // 患者端问诊
  { key:'patientInquiryList', test:(u,m)=>match(u,API.patientInquiryList)&&m==='GET', call:({data})=>handlers.patientInquiryList(data) },
  { key:'patientInquiryCreate', test:(u,m)=>match(u,API.patientInquiryCreate)&&m==='POST', call:({data})=>handlers.patientInquiryCreate(data) },
  { key:'patientInquiryDetail', test:(u,m)=>match(u,API.patientInquiryDetail)&&m==='GET', call:({data})=>handlers.patientInquiryDetail(data) },
  { key:'patientInquiryReply', test:(u,m)=>match(u,API.patientInquiryReply)&&m==='POST', call:({data})=>handlers.patientInquiryReply(data) },

  // 组/成员
  { key:'groups',         test:(u,m)=>match(u,API.groups)&&m==='GET',               call:()=>handlers.groups() },
  { key:'groupCreate',    test:(u,m)=>match(u,API.groupCreate)&&m==='POST',         call:({data})=>handlers.groupCreate(data) },
  { key:'groupOpen',      test:(u,m)=>match(u,API.groupOpen)&&m==='POST',           call:({data})=>handlers.groupOpen(data) },
  { key:'groupSetQuota',  test:(u,m)=>match(u,API.groupSetQuota)&&m==='POST',       call:({data})=>handlers.groupSetQuota(data) },
  { key:'groupAddMember', test:(u,m)=>match(u,API.groupAddMember)&&m==='POST',      call:({data})=>handlers.groupAddMember(data) },
  { key:'groupRemoveMember', test:(u,m)=>match(u,API.groupRemoveMember)&&m==='POST', call:({data})=>handlers.groupRemoveMember(data) },
  { key:'groupSetLeader', test:(u,m)=>match(u,API.groupSetLeader)&&m==='POST',      call:({data})=>handlers.groupSetLeader(data) },
  { key:'groupSetRole',   test:(u,m)=>match(u,API.groupSetRole)&&m==='POST',        call:({data})=>handlers.groupSetRole(data) },
  { key:'groupAddFromPool', test:(u,m)=>match(u,API.groupAddFromPool)&&m==='POST',  call:({data})=>handlers.groupAddFromPool(data) },
  { key:'groupJoinByCode', test:(u,m)=>match(u,API.groupJoinByCode)&&m==='POST',    call:({data})=>handlers.groupJoinByCode(data) },
  { key:'groupConfirmBinding', test:(u,m)=>match(u,API.groupConfirmBinding)&&m==='POST', call:({data})=>handlers.groupConfirmBinding(data) },
  { key:'groupCurrentBinding', test:(u,m)=>match(u,API.groupCurrentBinding)&&m==='GET', call:({data})=>handlers.groupCurrentBinding(data) },
  { key:'groupUnbind',    test:(u,m)=>match(u,API.groupUnbind)&&m==='POST',         call:({data})=>handlers.groupUnbind(data) },

  // 通用消息与任务
  { key:'messages',       test:(u,m)=>match(u,API.messages)&&m==='GET',             call:()=>handlers.messages() },
  { key:'patientMessages', test:(u,m)=>match(u,API.patientMessages)&&m==='GET',     call:({data})=>handlers.patientMessages(data) },

  { key:'tasksList',      test:(u,m)=>match(u,API.tasks)&&m==='GET',                call:()=>handlers.tasksList() },
  { key:'taskCreate',     test:(u,m)=>match(u,API.tasks)&&m==='POST',               call:({data})=>handlers.taskCreate(data) },
  { key:'taskDetail',     test:(u,m)=>startsWith(u,'/api/tasks/')&&m==='GET',       call:({url})=>handlers.taskDetail({id:url.split('/').pop()}) },

  // 队列
  { key:'queueStatus',    test:(u,m)=>match(u,API.queueStatus)&&m==='GET',          call:()=>handlers.queueStatus() },
  { key:'adminQueueListAll', test:(u,m)=>match(u,API.adminQueueListAll)&&m==='GET', call:({data})=>handlers.adminQueueListAll(data) },
  { key:'queueList',      test:(u,m)=> (match(u,API.queueList)||u.includes('/queues')) && m==='GET', call:()=>handlers.queueList() },
  { key:'queueItemDetail', test:(u,m)=> (match(u,API.queueItemDetail)||match(u,API.adminQueueItemDetail))&&m==='GET', call:({data})=>handlers.queueItemDetail({id:data?.id||data?.queueItemId||data?.queueId}) },
  { key:'queueItemUpdateStatus', test:(u,m)=> (match(u,API.queueItemUpdateStatus)||match(u,API.adminQueueItemUpdateStatus))&&m==='POST',
    call:({data})=>handlers.queueItemUpdateStatus({
      id:data?.id||data?.queueItemId||data?.queueId,
      status:data?.status, reason:data?.reason, operator:data?.operator, role:data?.role, boundDeptId:data?.boundDeptId
    }) },
  { key:'queueItemSetPriority', test:(u,m)=> (match(u,API.queueItemSetPriority)||match(u,API.adminQueueItemSetPriority))&&m==='POST',
    call:({data})=>handlers.queueItemSetPriority({id:data?.id||data?.queueItemId||data?.queueId, priority:data?.priority}) },
  { key:'adminQueueStats', test:(u,m)=>match(u,API.adminQueueStats)&&m==='GET',     call:({data})=>handlers.adminQueueStats(data) },
  { key:'adminQueueBroadcast', test:(u,m)=>match(u,API.adminQueueBroadcast)&&m==='POST', call:({data})=>handlers.adminQueueBroadcast(data) },
];

/* -------------------- 统一入口 -------------------- */
async function handle(a, b, c) {
  const { url, method, data } = normArgs(a, b, c);
  await sleep();
  const route = routes.find(r => r.test(url, method));
  if (!route) {
    if (startsWith(url, '/api/patients/') && method === 'GET') {
      return tryCatch(() => ok(handlers.patientDetail({ id: url.split('/').pop() })));
    }
    return ok({ ok: true, url, method, data, note: 'no mock branch matched; echo payload' });
  }
  return tryCatch(() => route.call({ url, method, data }));
}

module.exports = {
  handle, handlers, routes, store,
  utils: {
    now, sleep, clone, ok, err, tryCatch,
    normArgs, match, startsWith, toArr, uid,
    normStatus, normPriority,
    canTransit, findQueueItemById, computeQueueStats,
    getAllowedTransitions, getStatusClass, getStatusIcon
  }
};
