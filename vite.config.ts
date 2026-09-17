import tailwindcss from '@tailwindcss/postcss';
import vinext from 'vinext';
import { defineConfig } from 'vite';
export default defineConfig({css:{postcss:{plugins:[tailwindcss()]}},plugins:[vinext()],server:{host:'127.0.0.1',port:5173,watch:{useFsEvents:false,usePolling:true},proxy:{'/api':'http://127.0.0.1:8080','/photos':'http://127.0.0.1:8080'}}});
