// // 智能体教育等级
// enum Education {
//     // 未指定
//     EDUCATION_UNSPECIFIED = 0;
//     // 博士
//     EDUCATION_DOCTOR = 1;
//     // 硕士
//     EDUCATION_MASTER = 2;
//     // 本科
//     EDUCATION_BACHELOR = 3;
//     // 高中
//     EDUCATION_HIGH_SCHOOL = 4;
//     // 初中
//     EDUCATION_JUNIOR_HIGH_SCHOOL = 5;
//     // 小学
//     EDUCATION_PRIMARY_SCHOOL = 6;
//     // 大专
//     EDUCATION_COLLEGE = 7;
// }
export const PairEducation = [
    [1, "Doctorate"],
    [2, "Master"],
    [3, "Bachelor"],
    [4, "High school"],
    [5, "Junior high"],
    [6, "Primary school"],
    [7, "College diploma"],
]
export const MapEducation = new Map<number, string>(PairEducation as Iterable<readonly [number, string]>);

// // 智能体性别
// enum Gender {
//     // 未指定
//     GENDER_UNSPECIFIED = 0;
//     // 男性
//     GENDER_MALE = 1;
//     // 女性
//     GENDER_FEMALE = 2;
// }
export const PairGender = [
    [1, "Male"],
    [2, "Female"],
]
export const MapGender = new Map<number, string>(PairGender as Iterable<readonly [number, string]>);

// // 智能体消费水平
// enum Consumption {
//     // 未指定
//     CONSUMPTION_UNSPECIFIED = 0;
//     // 低
//     CONSUMPTION_LOW = 1;
//     // 较低
//     CONSUMPTION_RELATIVELY_LOW = 2;
//     // 中等
//     CONSUMPTION_MEDIUM = 3;
//     // 较高
//     CONSUMPTION_RELATIVELY_HIGH = 4;
//     // 高
//     CONSUMPTION_HIGH = 5;
// }
export const PairConsumption = [
    [1, "Low"],
    [2, "Relatively low"],
    [3, "Medium"],
    [4, "Relatively high"],
    [5, "High"],
];
export const MapConsumption = new Map<number, string>(PairConsumption as Iterable<readonly [number, string]>);

export const PairLandUse = [
    [0, 'Unspecified'],
    [5, 'Commercial land'],
    [6, 'Industrial and warehouse land'],
    [7, 'Residential land'],
    [8, 'Public service land'],
    [10, 'Transportation land'],
    [12, 'Other land'],
];
export const MapLandUse = new Map<number, string>(PairLandUse as Iterable<readonly [number, string]>);

export const GetEducationName = (education: number) => {
    return MapEducation.get(education) || "Unknown";
}

export const GetGenderName = (gender: number) => {
    return MapGender.get(gender) || "Unknown";
}

export const GetConsumptionName = (consumption: number) => {
    return MapConsumption.get(consumption) || "Unknown";
}

export const GetLandUseName = (landUse: number) => {
    return MapLandUse.get(landUse) || "Unknown";
}
