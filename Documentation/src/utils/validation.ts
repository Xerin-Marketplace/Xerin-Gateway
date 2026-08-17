export const isEmail = (value: string) => /\S+@\S+\.\S+/.test(value);

export const minLength = (value: string, length: number) => value.trim().length >= length;
