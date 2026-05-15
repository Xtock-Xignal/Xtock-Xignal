/** @type {import('next').NextConfig} */
const nextConfig = {
  webpack: (config, context) => {
    config.watchOptions = {
      poll: 1000, // 1초마다 파일 변경 사항 강제 확인
      aggregateTimeout: 300,
    };
    return config;
  },
};

export default nextConfig;