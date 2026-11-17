module.exports = function csvBucket() {
  const value = dataform.projectConfig.vars.csv_bucket;
  if (typeof value !== "string" || !/^[a-z0-9][a-z0-9._-]{1,221}[a-z0-9]$/.test(value)) {
    throw new Error("Set csv_bucket to a valid Cloud Storage bucket name.");
  }
  return value;
};
