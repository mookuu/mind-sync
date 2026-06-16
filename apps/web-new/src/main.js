import { createApp } from "vue";
import { createRouter, createWebHistory } from "vue-router";
import App from "./App.vue";
import routes from "./router/index.js";
import "./assets/styles/variables.css";
import "./assets/styles/base.css";
import "./assets/styles/components.css";

const router = createRouter({
  history: createWebHistory(),
  routes,
});

const app = createApp(App);

app.use(router);
app.mount("#app");
