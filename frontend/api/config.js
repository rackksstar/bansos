if (typeof module !== "undefined" && module.exports) {
  module.exports = (request, response) => {
    response.setHeader("Content-Type", "application/javascript; charset=utf-8");
    response.setHeader("Cache-Control", "no-store");
    response.send(
      `window.BANSOS_API_BASE_URL = ${JSON.stringify(
        process.env.BANSOS_API_BASE_URL || ""
      )};`
    );
  };
} else {
  window.BANSOS_API_BASE_URL = window.BANSOS_API_BASE_URL || "";
}
