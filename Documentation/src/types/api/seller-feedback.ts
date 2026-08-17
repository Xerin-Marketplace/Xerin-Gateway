export type SellerReviewStatus =
  | "pending"
  | "approved"
  | "rejected"
  | "reported"
  | string;

export type SellerReview = {
  id: string;
  rating: number;
  title?: string | null;
  comment?: string | null;
  verified_purchase: boolean;
  status: SellerReviewStatus;
  seller_reply?: string | null;
  seller_replied_at?: string | null;
  helpful_count: number;
  created_at: string;
  updated_at?: string | null;
};

export type SellerReviewList = {
  total: number;
  page: number;
  page_size: number;
  average_rating: number | string;
  results: SellerReview[];
};

export type SellerReviewReportReason =
  | "spam"
  | "abusive"
  | "fake"
  | "irrelevant"
  | "personal_information"
  | "other";

export type SellerQuestionStatus =
  | "published"
  | "pending"
  | "reported"
  | "hidden"
  | "rejected"
  | string;

export type SellerProductAnswer = {
  id: string;
  question_id: string;
  user_id: string;
  answer: string;
  is_seller_answer: boolean;
  is_official: boolean;
  status: SellerQuestionStatus;
  helpful_count: number;
  created_at: string;
  updated_at?: string | null;
};

export type SellerProductQuestion = {
  id: string;
  product_id: string;
  customer_id: string;
  question: string;
  status: SellerQuestionStatus;
  helpful_count: number;
  answer_count: number;
  created_at: string;
  updated_at?: string | null;
  answers: SellerProductAnswer[];
};

export type SellerQuestionList = {
  total: number;
  page: number;
  page_size: number;
  results: SellerProductQuestion[];
};
