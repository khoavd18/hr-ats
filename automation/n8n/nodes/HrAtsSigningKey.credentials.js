class HrAtsSigningKey {
  name = "hrAtsSigningKey";
  displayName = "HR ATS Webhook Signing";
  properties = [
    {
      displayName: "Signing Key",
      name: "secret",
      type: "string",
      typeOptions: { password: true },
      default: "",
      required: true,
    },
    {
      displayName: "ATS Web Origin",
      name: "origin",
      type: "string",
      default: "",
      required: true,
    },
  ];
}
module.exports = { HrAtsSigningKey };
