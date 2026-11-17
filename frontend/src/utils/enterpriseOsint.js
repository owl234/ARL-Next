/**
 * 企业生态资产 (OSINT) 统一字段解析与动态列裁剪工具
 * 供 EnterpriseOsintPanel 与 EnterpriseTaskDetailPanel 共享，确保双端口径一致且消除纯空白列。
 */

const hasText = (v) => v !== undefined && v !== null && String(v).trim() !== '';

export const getOsintDomain = (r) => r?.domain || r?.ym || '';

export const getOsintName = (r) =>
  r?.serviceName || r?.name || r?.webName || r?.title || r?.appName || '';

export const getOsintUnitName = (r) =>
  r?.unitName ||
  r?.companyName ||
  r?.miniProgramIcpRecordDetail?.icpFilingSubjectInformation?.organizingName ||
  r?.appIcpRecordDetail?.icpFilingSubjectInformation?.organizingName ||
  '';

export const getOsintCompanyType = (r) =>
  r?.companyType ||
  r?.natureName ||
  r?.miniProgramIcpRecordDetail?.icpFilingSubjectInformation?.natureName ||
  r?.appIcpRecordDetail?.icpFilingSubjectInformation?.natureName ||
  '';

export const getOsintLicence = (r) =>
  r?.serviceLicence || r?.liscense || r?.serviceFilingNumber || r?.mainLicence || '';

export const getOsintMainLicence = (r) =>
  r?.mainLicence ||
  r?.miniProgramIcpRecordDetail?.icpFilingSubjectInformation?.mainLicence ||
  r?.appIcpRecordDetail?.icpFilingSubjectInformation?.mainLicence ||
  '';

export const getOsintUpdateTime = (r) => r?.updateRecordTime || r?.examineDate || '';

export const getOsintHomeUrl = (r) => {
  if (r?.homeUrl) return r.homeUrl;
  if (r?.webSite) {
    if (Array.isArray(r.webSite) && r.webSite.length > 0) return r.webSite[0];
    if (typeof r.webSite === 'string') return r.webSite;
  }
  return '';
};

export const getOsintIcon = (r) =>
  r?.icon || r?.titleImgURL || r?.codeImg || r?.ico || r?.productLogo || r?.appLogo || '';

export const getOsintBrief = (r) => r?.brief || r?.recommend || r?.info || '';

export const getOsintCategory = (r) => r?.category || r?.classes || r?.type || '';

export const getOsintContentType = (r) =>
  r?.contentTypeName ||
  r?.appIcpRecordDetail?.contentTypeName ||
  r?.appIcpRecordDetail?.icpFilingServiceInformation?.contentTypeName ||
  r?.miniProgramIcpRecordDetail?.contentTypeName ||
  r?.miniProgramIcpRecordDetail?.icpFilingServiceInformation?.contentTypeName ||
  '';

export const getOsintWechatId = (r) => r?.wechatId || r?.publicNum || '';

export const getOsintLegalPerson = (r) => r?.legalPerson || r?.legalPersonName || '';

export const getOsintStatus = (r) => r?.status || r?.regStatus || '';

export const getOsintRegion = (r) =>
  r?.region || [r?.province, r?.city].filter(Boolean).join(' ') || '';

export const formatOsintDate = (val) => {
  if (!val) return '-';
  if (typeof val === 'number') {
    const d = new Date(val);
    if (!isNaN(d.getTime())) {
      return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    }
  }
  return String(val);
};

/**
 * 构建指定维度的自适应表格列：核心身份列常驻，数据源专属/低命中列仅在当前数据存在非空值时展示。
 */
export const buildEnterpriseOsintColumns = (t, tab, rows = [], options = {}) => {
  const {
    includeManagedStatus = false,
    includeAllOptional = false,
    indexWidth = 55,
    rawTitleKey = 'assets.rawData',
    rawWidth = 55,
    sortState = null,
  } = options;

  const list = Array.isArray(rows) ? rows : [];

  const updateTimeCol = () => {
    const col = {
      get title() { return t('assets.updatedAtLabel'); },
      dataIndex: 'updateRecordTime',
      key: 'updateRecordTime',
      width: 130,
      align: 'center',
    };
    if (sortState) {
      col.sorter = true;
      col.sortOrder = sortState.field === 'updateRecordTime' || sortState.field === 'examineDate' ? sortState.order : null;
    }
    return col;
  };

  const indexCol = {
    get title() { return t('tasks.no'); },
    key: 'index',
    width: indexWidth,
    align: 'center',
  };

  const rawCol = {
    get title() { return t(rawTitleKey); },
    key: 'raw',
    width: rawWidth,
    align: 'center',
  };

  const defsByTab = {
    web: [
      indexCol,
      { get title() { return t('tasks.domains'); }, dataIndex: 'domain', key: 'domain', width: 170 },
      ...(includeManagedStatus
        ? [{ get title() { return t('assets.managementStatus'); }, key: 'managedStatus', width: 95, align: 'center' }]
        : []),
      { get title() { return t('tasks.websiteName'); }, dataIndex: 'serviceName', key: 'serviceName', width: 160, ellipsis: true },
      { get title() { return t('assets.organization'); }, dataIndex: 'unitName', key: 'unitName', ellipsis: true },
      {
        get title() { return t('tasks.organizationType'); },
        dataIndex: 'companyType',
        key: 'companyType',
        width: 100,
        align: 'center',
        optional: true,
        hasValue: (r) => hasText(getOsintCompanyType(r)),
      },
      { get title() { return t('tasks.icpNumber'); }, dataIndex: 'serviceLicence', key: 'serviceLicence', width: 170 },
      {
        get title() { return t('assets.homeUrl'); },
        dataIndex: 'homeUrl',
        key: 'homeUrl',
        width: 170,
        ellipsis: true,
        optional: true,
        hasValue: (r) => hasText(getOsintHomeUrl(r)),
      },
      updateTimeCol(),
      rawCol,
    ],
    app: [
      indexCol,
      {
        get title() { return t('tasks.icon'); },
        dataIndex: 'icon',
        key: 'icon',
        width: 65,
        align: 'center',
        optional: true,
        hasValue: (r) => hasText(getOsintIcon(r)),
      },
      { get title() { return t('tasks.appName'); }, dataIndex: 'serviceName', key: 'serviceName', width: 170 },
      {
        get title() { return t('tasks.category'); },
        dataIndex: 'category',
        key: 'category',
        width: 100,
        optional: true,
        hasValue: (r) => hasText(getOsintCategory(r)),
      },
      { get title() { return t('tasks.icpNumber'); }, dataIndex: 'serviceLicence', key: 'serviceLicence', width: 170 },
      {
        get title() { return t('tasks.approvalType'); },
        dataIndex: 'contentTypeName',
        key: 'contentTypeName',
        width: 130,
        optional: true,
        hasValue: (r) => hasText(getOsintContentType(r)),
      },
      { get title() { return t('assets.organization'); }, dataIndex: 'unitName', key: 'unitName', ellipsis: true },
      {
        get title() { return t('tasks.description'); },
        dataIndex: 'brief',
        key: 'brief',
        ellipsis: true,
        optional: true,
        hasValue: (r) => hasText(getOsintBrief(r)),
      },
      {
        get title() { return t('assets.version'); },
        dataIndex: 'version',
        key: 'version',
        width: 90,
        align: 'center',
        optional: true,
        hasValue: (r) => hasText(r?.version),
      },
      updateTimeCol(),
      rawCol,
    ],
    mapp: [
      indexCol,
      {
        get title() { return t('tasks.icon'); },
        dataIndex: 'icon',
        key: 'icon',
        width: 65,
        align: 'center',
        optional: true,
        hasValue: (r) => hasText(getOsintIcon(r)),
      },
      { get title() { return t('tasks.miniProgramName'); }, dataIndex: 'serviceName', key: 'serviceName', width: 170 },
      { get title() { return t('tasks.icpNumber'); }, dataIndex: 'serviceLicence', key: 'serviceLicence', width: 170 },
      {
        get title() { return t('tasks.primaryIcpNumber'); },
        dataIndex: 'mainLicence',
        key: 'mainLicence',
        width: 155,
        optional: true,
        hasValue: (r) => hasText(getOsintMainLicence(r)) && getOsintMainLicence(r) !== getOsintLicence(r),
      },
      { get title() { return t('assets.organization'); }, dataIndex: 'unitName', key: 'unitName', ellipsis: true },
      {
        get title() { return t('tasks.category'); },
        dataIndex: 'category',
        key: 'category',
        width: 100,
        optional: true,
        hasValue: (r) => hasText(getOsintCategory(r)),
      },
      {
        get title() { return t('tasks.approvalType'); },
        dataIndex: 'contentTypeName',
        key: 'contentTypeName',
        width: 130,
        optional: true,
        hasValue: (r) => hasText(getOsintContentType(r)),
      },
      {
        get title() { return t('tasks.description'); },
        dataIndex: 'brief',
        key: 'brief',
        ellipsis: true,
        optional: true,
        hasValue: (r) => hasText(getOsintBrief(r)),
      },
      updateTimeCol(),
      rawCol,
    ],
    kapp: [
      indexCol,
      { get title() { return t('tasks.quickAppName'); }, dataIndex: 'serviceName', key: 'serviceName', width: 180 },
      { get title() { return t('tasks.icpNumber'); }, dataIndex: 'serviceLicence', key: 'serviceLicence', width: 180 },
      {
        get title() { return t('tasks.primaryIcpNumber'); },
        dataIndex: 'mainLicence',
        key: 'mainLicence',
        width: 160,
        optional: true,
        hasValue: (r) => hasText(getOsintMainLicence(r)) && getOsintMainLicence(r) !== getOsintLicence(r),
      },
      { get title() { return t('assets.organization'); }, dataIndex: 'unitName', key: 'unitName', ellipsis: true },
      {
        get title() { return t('tasks.approvalType'); },
        dataIndex: 'contentTypeName',
        key: 'contentTypeName',
        width: 140,
        optional: true,
        hasValue: (r) => hasText(getOsintContentType(r)),
      },
      updateTimeCol(),
      rawCol,
    ],
    wechat: [
      indexCol,
      {
        get title() { return t('tasks.avatar'); },
        dataIndex: 'icon',
        key: 'icon',
        width: 65,
        align: 'center',
        optional: true,
        hasValue: (r) => hasText(getOsintIcon(r)),
      },
      { get title() { return t('tasks.officialAccountName'); }, dataIndex: 'name', key: 'name', width: 170 },
      { get title() { return t('tasks.wechatId'); }, dataIndex: 'wechatId', key: 'wechatId', width: 150 },
      {
        get title() { return t('assets.qrCode'); },
        key: 'qrcode',
        width: 80,
        align: 'center',
        optional: true,
        hasValue: (r) => hasText(r?.codeImg),
      },
      {
        get title() { return t('assets.features'); },
        dataIndex: 'brief',
        key: 'brief',
        ellipsis: true,
        optional: true,
        hasValue: (r) => hasText(getOsintBrief(r)),
      },
      { get title() { return t('assets.verifiedOrganization'); }, dataIndex: 'unitName', key: 'unitName', ellipsis: true },
      rawCol,
    ],
    weibo: [
      indexCol,
      {
        get title() { return t('tasks.avatar'); },
        dataIndex: 'icon',
        key: 'icon',
        width: 65,
        align: 'center',
        optional: true,
        hasValue: (r) => hasText(getOsintIcon(r)),
      },
      { get title() { return t('assets.weiboName'); }, dataIndex: 'name', key: 'name', width: 170 },
      {
        get title() { return t('assets.verificationDescription'); },
        dataIndex: 'brief',
        key: 'brief',
        ellipsis: true,
        optional: true,
        hasValue: (r) => hasText(getOsintBrief(r)),
      },
      { get title() { return t('assets.weiboProfile'); }, dataIndex: 'href', key: 'href', width: 160 },
      {
        get title() { return t('assets.followers'); },
        dataIndex: 'fans',
        key: 'fans',
        width: 100,
        align: 'center',
        optional: true,
        hasValue: (r) => hasText(r?.fans),
      },
      rawCol,
    ],
    invest: [
      indexCol,
      { get title() { return t('assets.investeeCompany'); }, dataIndex: 'name', key: 'name', ellipsis: true },
      { get title() { return t('tasks.legalRepresentative'); }, dataIndex: 'legalPerson', key: 'legalPerson', width: 110 },
      { get title() { return t('tasks.ownershipShare'); }, dataIndex: 'percent', key: 'percent', width: 100, align: 'center' },
      { get title() { return t('assets.investmentAmount'); }, dataIndex: 'amount', key: 'amount', width: 140 },
      {
        get title() { return t('assets.companyStatus'); },
        dataIndex: 'status',
        key: 'status',
        width: 100,
        align: 'center',
        optional: true,
        hasValue: (r) => hasText(getOsintStatus(r)),
      },
      {
        get title() { return t('assets.region'); },
        dataIndex: 'region',
        key: 'region',
        width: 130,
        optional: true,
        hasValue: (r) => hasText(getOsintRegion(r)),
      },
      {
        get title() { return t('assets.establishedOn'); },
        dataIndex: 'estiblishTime',
        key: 'estiblishTime',
        width: 120,
        align: 'center',
        optional: true,
        hasValue: (r) => hasText(r?.estiblishTime),
      },
      rawCol,
    ],
  };

  const cols = defsByTab[tab] || defsByTab.web;
  return cols
    .filter((col) => {
      if (!col.optional || includeAllOptional) return true;
      if (list.length === 0) return false;
      return list.some(col.hasValue);
    })
    .map(({ optional, hasValue, ...rest }) => rest);
};
