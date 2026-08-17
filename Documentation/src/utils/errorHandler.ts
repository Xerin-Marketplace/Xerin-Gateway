export const getReadableError = (error: unknown) => {
  if (error instanceof Error) return error.message;
  return "Something went wrong";
};
