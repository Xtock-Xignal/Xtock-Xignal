FROM node:20-alpine

WORKDIR /app

COPY package*.json ./
RUN npm install
 
COPY . .

# Vitest 및 기타 devDependencies를 컨테이너 내부에서 즉시 사용 가능하도록
# 별도 호스트 설치 없이 동작하도록 의존성을 같이 설치합니다.
CMD ["npm", "run", "dev"]
# CMD ["tail", "-f", "/dev/null"]
