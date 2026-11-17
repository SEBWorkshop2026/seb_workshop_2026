module.exports = function reportingDate() {
  const value = dataform.projectConfig.vars.reporting_period;
  if (typeof value !== "string" || !/^(?!0000)\d{4}-(0[1-9]|1[0-2])$/.test(value)) {
    throw new Error("Set reporting_period to a month in YYYY-MM format.");
  }
  return `${value}-01`;
};
