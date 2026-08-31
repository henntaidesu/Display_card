// 部件类型各自的录入口径：品牌候选、型号提示、「规格」这一栏到底填什么。
//
// 为什么要分类型：CPU 的品牌只可能是 Intel / AMD，硬盘的「规格」是容量+接口，电源的
// 是功率，主板的是芯片组——摆一个统一的「品牌 / 规格」文本框，等于每次都要靠人自己
// 回忆该写什么、写成什么格式，几台机器之后同一个东西就会有三种写法，之后再想按容量
// 或功率统计就全乱了。
//
// 候选值一律用拉丁文/中性写法（ASUS、1TB NVMe、850W），三种界面语言下都不用翻译，
// 也和日本站上的原始标注对得上。除 CPU 外都允许现场输入清单外的值（filterable +
// allow-create），清单只是省事的默认项，不是白名单。

// 新建整机时默认列出的六个部件槽位，顺序即表单里的显示顺序。
// 这六样是一台机器几乎必然有的东西，不该让人每次都点六下「快捷添加」。
export const DEFAULT_PART_TYPES = ['cpu', 'gpu', 'ram', 'disk', 'motherboard', 'psu']

export const PART_SCHEMA = {
  cpu: {
    // 用户明确要求：CPU 品牌只有这两个，所以不允许现场新建
    brands: ['Intel', 'AMD'],
    brandStrict: true,
    modelPlaceholder: 'i9-13900K / R9 7950X',
    specs: []          // 频率、核心数写法太散，留成自由文本
  },
  gpu: {
    // 显卡的品牌与型号走系统里已有的字典（系统配置 → 品牌/型号），下面这份只是字典为空时的兜底
    brands: ['ASUS', 'MSI', 'GIGABYTE', 'ZOTAC', 'PALIT', 'INNO3D', 'COLORFUL', 'GALAX', 'NVIDIA'],
    brandStrict: false,
    modelPlaceholder: 'RTX 4090',
    specs: ['8GB', '12GB', '16GB', '20GB', '24GB', '32GB']
  },
  ram: {
    brands: ['Kingston', 'Corsair', 'G.SKILL', 'Crucial', 'ADATA', 'Samsung', 'SK hynix', 'Micron', 'TEAM'],
    brandStrict: false,
    modelPlaceholder: 'Fury / Vengeance',
    specs: [
      '8GB DDR4', '16GB DDR4', '32GB DDR4',
      '16GB DDR5', '32GB DDR5', '48GB DDR5', '64GB DDR5',
      '16GB DDR3', '32GB ECC'
    ]
  },
  disk: {
    brands: ['Samsung', 'Western Digital', 'Seagate', 'KIOXIA', 'Crucial', 'SanDisk', 'Intel', 'ADATA'],
    brandStrict: false,
    modelPlaceholder: '990 PRO / SN850X',
    specs: [
      '256GB NVMe', '512GB NVMe', '1TB NVMe', '2TB NVMe', '4TB NVMe',
      '256GB SATA SSD', '512GB SATA SSD', '1TB SATA SSD', '2TB SATA SSD',
      '1TB HDD', '2TB HDD', '4TB HDD', '8TB HDD'
    ]
  },
  motherboard: {
    brands: ['ASUS', 'MSI', 'GIGABYTE', 'ASRock', 'BIOSTAR', 'COLORFUL'],
    brandStrict: false,
    modelPlaceholder: 'ROG STRIX B650-A',
    specs: [
      'B450', 'B550', 'X570', 'B650', 'X670', 'B850', 'X870',
      'H610', 'B660', 'B760', 'B860', 'Z690', 'Z790', 'Z890', 'C621'
    ]
  },
  psu: {
    brands: ['Seasonic', 'Corsair', 'Super Flower', 'Cooler Master', 'Antec', 'EVGA', 'be quiet!', 'Great Wall'],
    brandStrict: false,
    modelPlaceholder: 'FOCUS GX-850',
    specs: ['450W', '550W', '650W', '750W', '850W', '1000W', '1200W', '1600W']
  },
  cooler: {
    brands: ['Thermalright', 'Noctua', 'DeepCool', 'Cooler Master', 'Corsair', 'be quiet!', 'NZXT'],
    brandStrict: false,
    modelPlaceholder: 'AK620 / H150i',
    specs: ['Air', '120mm AIO', '240mm AIO', '280mm AIO', '360mm AIO', '420mm AIO']
  },
  case: {
    brands: ['Lian Li', 'Fractal Design', 'NZXT', 'Cooler Master', 'Corsair', 'Antec', 'SAMA'],
    brandStrict: false,
    modelPlaceholder: 'O11 Dynamic',
    specs: ['ATX', 'MATX', 'ITX', 'E-ATX']
  },
  other: {
    brands: [],
    brandStrict: false,
    modelPlaceholder: '',
    specs: []
  }
}

export function partSchema(partType) {
  return PART_SCHEMA[partType] || PART_SCHEMA.other
}

// 「规格」这一栏的标题按类型换（显存 / 容量 / 功率 / 芯片组…），i18n 里对应
// partSpec.<type>；没有单独定义的类型退回 partSpec.other。
export function specLabelKey(partType) {
  return 'partSpec.' + (PART_SCHEMA[partType] ? partType : 'other')
}
